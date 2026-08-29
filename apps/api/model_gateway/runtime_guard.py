"""Production runtime hardening for the model gateway.

The gateway previously logged cost metrics only to application logs while the
monthly safety guard queried ``llm_usage_log``. No production call site wrote
that table, so cumulative cost enforcement effectively always saw zero. Arena
streaming also bypassed ``check_credit_and_cost_safety`` entirely.

This guard makes provider accounting a closed loop:

* estimate the full call (input + maximum output) conservatively before work;
* run the existing gateway with an AsyncSession even when a caller supplied a
  synchronous SQLModel Session, avoiding cross-thread Session use;
* persist the actual GatewayModelCallResult to LLMUsageLog after every call,
  including failed streams that consumed tokens/cost;
* account every returned token total immediately in the daily quota counter
  with a per-call settled UsageLedgerEntry, so failed provider calls count too;
* apply the same preflight/persistence path to streaming Arena calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from model_gateway.types import GatewayModelCallResult, GatewayRequest

logger = logging.getLogger(__name__)

_installed = False
_original_route_call = None
_original_route_stream = None


def _resolved_litellm_model(model_id: str) -> str:
    try:
        from model_gateway.model_map import MODEL_MAP, resolve_model_key

        canonical = resolve_model_key(model_id)
        mapped = MODEL_MAP.get(canonical)
        if mapped and mapped.get("litellm_model"):
            return str(mapped["litellm_model"])
        return canonical
    except Exception:
        return model_id


def estimate_full_call_cost(
    *,
    messages: list[dict[str, Any]],
    model_id: str,
    max_tokens: int,
) -> float:
    """Estimate worst-case call cost before provider execution.

    LiteLLM pricing is preferred. If model pricing/tokenization is unavailable,
    fall back to a deliberately conservative $30 / 1M-token assumption for
    both input and the full configured output budget.
    """
    model = _resolved_litellm_model(model_id)
    output_budget = max(int(max_tokens or 0), 0)
    try:
        from litellm import cost_per_token, token_counter

        input_tokens = max(int(token_counter(model=model, messages=messages) or 0), 0)
        prompt_cost, completion_cost = cost_per_token(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_budget,
        )
        estimate = max(float(prompt_cost or 0.0) + float(completion_cost or 0.0), 0.0)
        if estimate > 0:
            return estimate
    except Exception:
        logger.debug("Gateway pricing estimate unavailable for %s", model, exc_info=True)

    approx_chars = len(str(messages))
    input_tokens = max(1, approx_chars // 4)
    return 0.00003 * float(input_tokens + output_budget)


async def _preflight_cost(
    *,
    user_id: str | None,
    user_plan: str | None,
    messages: list[dict[str, Any]],
    model_id: str,
    max_tokens: int,
) -> float:
    estimate = estimate_full_call_cost(
        messages=messages,
        model_id=model_id,
        max_tokens=max_tokens,
    )
    if not user_id:
        from model_gateway.costs import check_credit_and_cost_safety

        await check_credit_and_cost_safety(None, user_plan, estimate, None)
        return estimate

    from database_async import async_session_scope
    from model_gateway.costs import check_credit_and_cost_safety

    async with async_session_scope() as session:
        await check_credit_and_cost_safety(
            user_id,
            user_plan,
            estimate,
            session,
        )
    return estimate


def _safe_error_message(result: GatewayModelCallResult) -> str | None:
    if not result.error_message:
        return None
    try:
        from llm_errors import classify_provider_exception

        return classify_provider_exception(Exception(result.error_message)).message[:500]
    except Exception:
        return "Model provider call failed."


def _resolve_attempt_id_sync(session, debate_id: str | None) -> str | None:
    if not debate_id:
        return None

    from models import Debate, DebateAttempt
    from orchestration.execution_context import get_current_execution_lease
    from sqlmodel import select

    lease = get_current_execution_lease()
    attempt_number: int | None = None
    if lease is not None and lease.debate_id == debate_id:
        attempt_number = max(int(lease.run_attempt or 0), 1)
    else:
        debate = session.get(Debate, debate_id)
        if debate is not None:
            attempt_number = max(int(debate.run_attempt or 0), 1)

    if attempt_number is None:
        return None
    attempt = session.exec(
        select(DebateAttempt).where(
            DebateAttempt.debate_id == debate_id,
            DebateAttempt.attempt_number == attempt_number,
        )
    ).first()
    return attempt.id if attempt is not None else None


def _persist_gateway_usage_sync(
    *,
    result: GatewayModelCallResult,
    user_id: str | None,
    debate_id: str | None,
    role: str | None,
    user_plan: str | None,
    preflight_estimate: float,
) -> None:
    from database import session_scope
    from models import LLMUsageLog, UsageLedgerEntry

    total_tokens = max(int(result.total_tokens or 0), 0)
    with session_scope() as session:
        attempt_id = _resolve_attempt_id_sync(session, debate_id)
        usage_log = LLMUsageLog(
            debate_id=debate_id,
            user_id=user_id,
            provider=result.provider or "unknown",
            model=result.model_used or "unknown",
            prompt_tokens=max(int(result.prompt_tokens or 0), 0),
            completion_tokens=max(int(result.completion_tokens or 0), 0),
            total_tokens=total_tokens,
            cost_usd=max(float(result.cost_usd or 0.0), 0.0),
            gateway=result.gateway,
            model_pool=result.model_pool,
            routing_policy=result.routing_policy,
            fallback_used=bool(result.fallback_used),
            fallback_reason=(result.fallback_reason or "")[:500] or None,
            user_plan=user_plan or result.user_plan,
            estimated_cost_usd=max(
                float(result.estimated_cost_usd or 0.0),
                float(preflight_estimate or 0.0),
            ),
            retry_count=max(int(result.retry_count or 0), 0),
            role=role,
            latency_ms=max(float(result.latency_ms or 0.0), 0.0),
            success=bool(result.success),
            error_message=_safe_error_message(result),
        )
        session.add(usage_log)
        session.flush()

        if user_id and total_tokens > 0:
            # Per-call ledger identity is generated from the already-durable
            # usage-log identity. The quota increment and settled ledger row are
            # part of the same transaction, so retry cannot double-count.
            token_entry = UsageLedgerEntry(
                user_id=user_id,
                kind="gateway_token_usage",
                status="settled",
                idempotency_key=f"gateway_token:{usage_log.id}",
                amount=total_tokens,
                debate_id=debate_id,
                attempt_id=attempt_id,
                meta={
                    "llm_usage_log_id": usage_log.id,
                    "provider": result.provider,
                    "model": result.model_used,
                    "success": bool(result.success),
                },
            )
            session.add(token_entry)

            from usage_limits import record_token_usage as apply_daily_token_usage

            apply_daily_token_usage(
                session,
                user_id,
                total_tokens,
                commit=False,
            )
        session.commit()


async def persist_gateway_usage(
    *,
    result: GatewayModelCallResult,
    user_id: str | None,
    debate_id: str | None,
    role: str | None,
    user_plan: str | None,
    preflight_estimate: float,
) -> None:
    """Persist cost and per-call token quota in a fresh owned sync Session."""
    if result.provider == "mock":
        return
    await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: _persist_gateway_usage_sync(
            result=result,
            user_id=user_id,
            debate_id=debate_id,
            role=role,
            user_plan=user_plan,
            preflight_estimate=preflight_estimate,
        ),
    )


async def guarded_route_llm_call(request: GatewayRequest, db_session=None) -> GatewayModelCallResult:
    """Cost-guard and persist a non-streaming gateway call."""
    from sqlalchemy.ext.asyncio import AsyncSession

    estimate = await _preflight_cost(
        user_id=request.user_id,
        user_plan=request.user_plan,
        messages=request.messages,
        model_id=request.model_id,
        max_tokens=request.max_tokens,
    )

    # Existing route logic reads plan/BYOK/credit state from db_session. Never
    # let it move a synchronous request-owned Session into executor threads;
    # provide a fresh AsyncSession instead.
    if db_session is not None and isinstance(db_session, AsyncSession):
        result = await _original_route_call(request, db_session=db_session)
    else:
        from database_async import async_session_scope

        async with async_session_scope() as session:
            result = await _original_route_call(request, db_session=session)

    try:
        await persist_gateway_usage(
            result=result,
            user_id=request.user_id,
            debate_id=request.debate_id,
            role=request.role,
            user_plan=request.user_plan,
            preflight_estimate=estimate,
        )
    except Exception as exc:
        from config import settings

        logger.exception("gateway.usage_persistence_failed")
        if settings.APP_ENV in {"production", "staging"}:
            raise RuntimeError("Model usage accounting is temporarily unavailable.") from exc
    return result


async def guarded_route_llm_stream(
    *,
    messages: list[dict[str, str]],
    model_id: str,
    temperature: float = 0.7,
    max_tokens: int = 1200,
    on_delta=None,
    debate_id: str | None = None,
    user_id: str | None = None,
    api_key: str | None = None,
) -> GatewayModelCallResult:
    """Apply cumulative cost enforcement and persistence to Arena streaming."""
    user_plan: str | None = None
    if user_id:
        try:
            from billing.service import get_active_plan
            from database import session_scope

            with session_scope() as session:
                plan = get_active_plan(session, user_id)
                user_plan = plan.slug if plan else None
        except Exception:
            logger.warning("Failed to resolve stream user plan", exc_info=True)

    estimate = await _preflight_cost(
        user_id=user_id,
        user_plan=user_plan,
        messages=messages,
        model_id=model_id,
        max_tokens=max_tokens,
    )

    result = await _original_route_stream(
        messages=messages,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        on_delta=on_delta,
        debate_id=debate_id,
        user_id=user_id,
        api_key=api_key,
    )

    try:
        await persist_gateway_usage(
            result=result,
            user_id=user_id,
            debate_id=debate_id,
            role="arena_stream",
            user_plan=user_plan,
            preflight_estimate=estimate,
        )
    except Exception as exc:
        from config import settings

        logger.exception("gateway.stream_usage_persistence_failed")
        if settings.APP_ENV in {"production", "staging"}:
            raise RuntimeError("Model usage accounting is temporarily unavailable.") from exc
    return result


def install_gateway_runtime_guard() -> None:
    """Patch the canonical module-level gateway routes exactly once."""
    global _installed, _original_route_call, _original_route_stream
    if _installed:
        return

    import model_gateway

    _original_route_call = model_gateway.route_llm_call
    _original_route_stream = model_gateway.route_llm_stream
    model_gateway.route_llm_call = guarded_route_llm_call
    model_gateway.route_llm_stream = guarded_route_llm_stream
    _installed = True
