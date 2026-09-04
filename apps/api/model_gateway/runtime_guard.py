"""Production runtime hardening for the model gateway.

The gateway is treated as one accounting transaction that may contain multiple
provider attempts. A conservative cost/token slice is reserved before the first
adapter call; every later direct-model/OpenRouter fallback attempt extends that
reservation before provider work. Adapter results are then aggregated so failed
primary usage cannot disappear when a fallback succeeds.

The same boundary also deduplicates the historical Agent usage logger and is
installed lazily from agent_bridge for independently-loaded Celery workers.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from model_gateway.types import (
    GatewayModelCallResult,
    GatewayModelRestrictedError,
    GatewayQuotaExceededError,
    GatewayRequest,
)

logger = logging.getLogger(__name__)

_installed = False
_original_route_call = None
_original_route_stream = None
_original_legacy_usage_persist = None


def gateway_runtime_guard_installed() -> bool:
    return _installed


def mark_usage_call_persisted(call_usage: Any) -> None:
    try:
        setattr(call_usage, "_gateway_usage_persisted", True)
    except Exception:
        pass


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


def estimate_full_call_tokens(
    *,
    messages: list[dict[str, Any]],
    model_id: str,
    max_tokens: int,
) -> int:
    """Conservative pre-provider token reservation: input + full output cap."""
    output_budget = max(int(max_tokens or 0), 0)
    model = _resolved_litellm_model(model_id)
    try:
        from litellm import token_counter

        input_tokens = max(int(token_counter(model=model, messages=messages) or 0), 0)
    except Exception:
        input_tokens = max(1, len(str(messages)) // 4)
    return input_tokens + output_budget


def estimate_full_call_cost(
    *,
    messages: list[dict[str, Any]],
    model_id: str,
    max_tokens: int,
) -> float:
    """Estimate worst-case call cost using input plus full output budget."""
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

    return 0.00003 * float(
        estimate_full_call_tokens(
            messages=messages,
            model_id=model_id,
            max_tokens=max_tokens,
        )
    )


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
    """Unreserved persistence path (primarily anonymous/legacy execution)."""
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

            apply_daily_token_usage(session, user_id, total_tokens, commit=False)
        session.commit()


async def _reserve_budget(
    *,
    user_id: str | None,
    debate_id: str | None,
    model_id: str,
    role: str | None,
    user_plan: str | None,
    messages: list[dict[str, Any]],
    max_tokens: int,
):
    estimate = estimate_full_call_cost(
        messages=messages,
        model_id=model_id,
        max_tokens=max_tokens,
    )
    token_estimate = estimate_full_call_tokens(
        messages=messages,
        model_id=model_id,
        max_tokens=max_tokens,
    )

    if not user_id:
        from model_gateway.costs import check_credit_and_cost_safety

        await check_credit_and_cost_safety(None, user_plan, estimate, None)
        return estimate, token_estimate, None

    from model_gateway.reservations import reserve_gateway_budget_sync

    reservation = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: reserve_gateway_budget_sync(
            user_id=user_id,
            debate_id=debate_id,
            model_id=model_id,
            role=role,
            user_plan=user_plan,
            estimated_cost_usd=estimate,
            estimated_tokens=token_estimate,
        ),
    )
    return estimate, token_estimate, reservation


async def _settle_or_persist(
    *,
    reservation,
    result: GatewayModelCallResult,
    user_id: str | None,
    debate_id: str | None,
    role: str | None,
    user_plan: str | None,
    preflight_estimate: float,
) -> None:
    if reservation is not None:
        from model_gateway.reservations import settle_gateway_budget_sync

        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: settle_gateway_budget_sync(
                reservation,
                result=result,
                safe_error_message=_safe_error_message(result),
            ),
        )
        return

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


async def _release_preprovider_reservation(reservation, reason: str) -> None:
    if reservation is None:
        return
    from model_gateway.reservations import release_gateway_budget_sync

    await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: release_gateway_budget_sync(
            reservation,
            reason=reason,
        ),
    )


def _patch_adapter_method(adapter_cls, method_name: str) -> None:
    """Wrap an adapter method so every direct/fallback attempt is accounted."""
    original = getattr(adapter_cls, method_name, None)
    if original is None or getattr(original, "_accounting_guard_wrapped", False):
        return
    signature = inspect.signature(original)

    async def wrapped(self, *args, **kwargs):
        from model_gateway.attempt_tracker import (
            begin_adapter_attempt,
            finish_adapter_attempt,
        )

        try:
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            messages = bound.arguments.get("messages") or []
            model_id = str(bound.arguments.get("model_id") or "unknown")
            max_tokens = int(bound.arguments.get("max_tokens") or 0)
        except Exception:
            messages = []
            model_id = "unknown"
            max_tokens = 0

        index = await begin_adapter_attempt(
            messages=messages,
            model_id=model_id,
            max_tokens=max_tokens,
        )
        try:
            result = await original(self, *args, **kwargs)
        except Exception:
            finish_adapter_attempt(index, raised=True)
            raise
        finish_adapter_attempt(index, result=result)
        return result

    wrapped._accounting_guard_wrapped = True  # type: ignore[attr-defined]
    wrapped.__name__ = getattr(original, "__name__", method_name)
    wrapped.__doc__ = getattr(original, "__doc__", None)
    setattr(adapter_cls, method_name, wrapped)


async def _execute_guarded_route(
    *,
    route_call,
    user_id: str | None,
    debate_id: str | None,
    model_id: str,
    role: str | None,
    user_plan: str | None,
    messages: list[dict[str, Any]],
    max_tokens: int,
):
    """Run one gateway route inside reservation + adapter-attempt contexts."""
    from model_gateway.attempt_tracker import (
        GatewayAttemptContext,
        aggregate_accounting_result,
        bind_attempt_context,
        reset_attempt_context,
    )
    from model_gateway.costs import bind_cost_reservation, reset_cost_reservation

    estimate, token_estimate, reservation = await _reserve_budget(
        user_id=user_id,
        debate_id=debate_id,
        model_id=model_id,
        role=role,
        user_plan=user_plan,
        messages=messages,
        max_tokens=max_tokens,
    )
    attempt_context = GatewayAttemptContext(
        user_id=user_id,
        debate_id=debate_id,
        user_plan=user_plan,
        role=role,
        initial_cost_usd=estimate,
        initial_tokens=token_estimate,
        reservation=reservation,
    )
    attempt_token = bind_attempt_context(attempt_context)
    cost_token = (
        bind_cost_reservation(user_id, reservation.reserved_cost_usd)
        if reservation is not None and user_id
        else None
    )

    try:
        try:
            result = await route_call()
        except (GatewayQuotaExceededError, GatewayModelRestrictedError) as exc:
            # If no adapter started, this is a known pre-provider rejection and
            # the initial reservation is safe to release. If an adapter already
            # ran, keep its conservative accounting and let the caller fail.
            if not attempt_context.records:
                await _release_preprovider_reservation(
                    attempt_context.reservation,
                    type(exc).__name__,
                )
            raise
    finally:
        if cost_token is not None:
            reset_cost_reservation(cost_token)
        reset_attempt_context(attempt_token)

    active_reservation = attempt_context.reservation
    if not attempt_context.records and active_reservation is not None:
        # Circuit-open / missing-credential / validation failures can be returned
        # as friendly GatewayModelCallResult objects without invoking an adapter.
        await _release_preprovider_reservation(
            active_reservation,
            result.error_code or "no_provider_attempt",
        )
        return result, estimate, None

    aggregated = aggregate_accounting_result(result, attempt_context)
    return aggregated, estimate, active_reservation


async def guarded_route_llm_call(request: GatewayRequest, db_session=None) -> GatewayModelCallResult:
    """Reserve → account every adapter attempt → settle one non-streaming route."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async def route_call():
        if db_session is not None and isinstance(db_session, AsyncSession):
            return await _original_route_call(request, db_session=db_session)
        from database_async import async_session_scope

        async with async_session_scope() as session:
            return await _original_route_call(request, db_session=session)

    result, estimate, reservation = await _execute_guarded_route(
        route_call=route_call,
        user_id=request.user_id,
        debate_id=request.debate_id,
        model_id=request.model_id,
        role=request.role,
        user_plan=request.user_plan,
        messages=request.messages,
        max_tokens=request.max_tokens,
    )

    try:
        await _settle_or_persist(
            reservation=reservation,
            result=result,
            user_id=request.user_id,
            debate_id=request.debate_id,
            role=request.role,
            user_plan=request.user_plan,
            preflight_estimate=estimate,
        )
    except Exception as exc:
        from config import settings

        logger.exception("gateway.usage_settlement_failed")
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
    """Streaming path with the same per-attempt reservation/accounting contract."""
    user_plan: str | None = None
    if user_id:
        def _resolve_user_plan() -> str | None:
            from billing.service import get_active_plan
            from database import session_scope

            with session_scope() as session:
                plan = get_active_plan(session, user_id)
                return plan.slug if plan else None

        try:
            user_plan = await asyncio.get_running_loop().run_in_executor(
                None,
                _resolve_user_plan,
            )
        except Exception:
            logger.warning("Failed to resolve stream user plan", exc_info=True)

    async def route_call():
        return await _original_route_stream(
            messages=messages,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            on_delta=on_delta,
            debate_id=debate_id,
            user_id=user_id,
            api_key=api_key,
        )

    result, estimate, reservation = await _execute_guarded_route(
        route_call=route_call,
        user_id=user_id,
        debate_id=debate_id,
        model_id=model_id,
        role="arena_stream",
        user_plan=user_plan,
        messages=messages,
        max_tokens=max_tokens,
    )

    try:
        await _settle_or_persist(
            reservation=reservation,
            result=result,
            user_id=user_id,
            debate_id=debate_id,
            role="arena_stream",
            user_plan=user_plan,
            preflight_estimate=estimate,
        )
    except Exception as exc:
        from config import settings

        logger.exception("gateway.stream_usage_settlement_failed")
        if settings.APP_ENV in {"production", "staging"}:
            raise RuntimeError("Model usage accounting is temporarily unavailable.") from exc
    return result


async def _dedupe_legacy_usage_persist(call_usage, **kwargs) -> None:
    if getattr(call_usage, "_gateway_usage_persisted", False):
        return
    if _original_legacy_usage_persist is not None:
        await _original_legacy_usage_persist(call_usage, **kwargs)


def install_gateway_runtime_guard() -> None:
    """Patch routes, adapter attempts, and legacy duplicate persistence once."""
    global _installed, _original_route_call, _original_route_stream, _original_legacy_usage_persist
    if _installed:
        return

    import model_gateway
    from model_gateway.adapters import DirectProviderAdapter, MockAdapter, OpenRouterAdapter

    _original_route_call = model_gateway.route_llm_call
    _original_route_stream = model_gateway.route_llm_stream
    model_gateway.route_llm_call = guarded_route_llm_call
    model_gateway.route_llm_stream = guarded_route_llm_stream

    for adapter_cls in (DirectProviderAdapter, OpenRouterAdapter, MockAdapter):
        _patch_adapter_method(adapter_cls, "call_llm")
        _patch_adapter_method(adapter_cls, "stream_llm")

    try:
        import agents

        _original_legacy_usage_persist = agents.persist_usage_log
        agents.persist_usage_log = _dedupe_legacy_usage_persist
    except Exception:
        logger.warning("Could not install legacy usage persistence dedupe", exc_info=True)

    _installed = True
