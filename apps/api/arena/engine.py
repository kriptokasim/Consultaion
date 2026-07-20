"""Arena mode engine: fan-out to SOTA models, collect answers, synthesize verdict."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List

from agents import UsageAccumulator, call_llm_for_role
from database_async import async_session_scope
from models import Debate, Message
from parliament.model_registry import get_arena_models
from sse_backend import get_sse_backend

from arena.prompts import (
    get_compiled_model_prompt,
)

from observability.latency import (
    PROMETHEUS_AVAILABLE,
    record_connect_latency,
    record_model_latency,
    record_stream_dps,
    record_stream_duration,
    record_ttft,
)

logger = logging.getLogger(__name__)

MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1


def _derive_model_family(model_info) -> str:
    if model_info.litellm_model and "/" in model_info.litellm_model:
        return model_info.litellm_model.split("/", 1)[1]
    return model_info.id


@dataclass
class ArenaModelResponse:
    """Individual model response in an arena run."""
    model_id: str
    display_name: str
    provider: str
    content: str
    success: bool
    logo_url: str | None = None
    persona_type: str | None = None
    persona_tagline: str | None = None
    error: str | None = None
    error_code: str | None = None
    response_id: str | None = None
    run_attempt: int = 1
    retry_generation: int = 0


async def persist_and_publish_arena_response(
    session,
    backend,
    debate_id: str,
    response: ArenaModelResponse,
) -> None:
    """Persist the arena model response to the database with idempotency check, and stream it to SSE."""
    from sqlmodel import select
    # 1. Idempotency check: load existing messages for this debate and role 'arena_response'
    stmt = select(Message).where(Message.debate_id == debate_id).where(Message.role == "arena_response")
    res = await session.execute(stmt)
    existing_messages = res.scalars().all()
    
    already_exists = False
    for msg in existing_messages:
        meta = msg.meta if isinstance(msg.meta, dict) else {}
        existing_attempt = int(meta.get("run_attempt", 1) or 1)
        existing_generation = int(meta.get("retry_generation", 0) or 0)
        same_response_id = bool(
            response.response_id and meta.get("response_id") == response.response_id
        )
        same_attempt = (
            meta.get("model_id") == response.model_id
            and existing_attempt == response.run_attempt
            and existing_generation == response.retry_generation
        )
        if same_response_id or same_attempt:
            already_exists = True
            break
            
    if not already_exists:
        session.add(
            Message(
                debate_id=debate_id,
                round_index=1,
                role="arena_response",
                persona=response.display_name,
                content=response.content,
                meta={
                    "model_id": response.model_id,
                    "display_name": response.display_name,
                    "provider": response.provider,
                    "mode": "arena",
                    "response_id": response.response_id,
                    "run_attempt": response.run_attempt,
                    "retry_generation": response.retry_generation,
                    "logo_url": response.logo_url,
                    "persona_type": response.persona_type,
                    "persona_tagline": response.persona_tagline,
                    "success": response.success,
                    "error": response.error or (None if response.success else "Model failed to respond"),
                    "error_code": response.error_code,
                },
            )
        )
        await session.commit()
    
    # 2. Publish to SSE
    await backend.publish(
        f"debate:{debate_id}",
        {
            "type": "arena_response",
            "debate_id": str(debate_id),
            "model_id": response.model_id,
            "response_id": response.response_id,
            "display_name": response.display_name,
            "provider": response.provider,
            "content": response.content,
            "logo_url": response.logo_url,
            "persona_type": response.persona_type,
            "persona_tagline": response.persona_tagline,
            "success": response.success,
            "error": response.error or (None if response.success else "Model failed to respond"),
            "error_code": response.error_code,
            "run_attempt": response.run_attempt,
            "retry_generation": response.retry_generation,
        },
    )


@dataclass
class ArenaResult:
    """Result of an arena run."""
    final_answer: str
    final_meta: dict
    usage_tracker: UsageAccumulator
    status: str
    error_reason: str | None = None
    model_responses: List[ArenaModelResponse] = field(default_factory=list)


async def run_arena(
    debate_id: str,
    *,
    model_id: str | None = None,
    continue_pipeline: bool = False,
    execution_owner_id: str | None = None,
    lease_epoch: int | None = None,
) -> ArenaResult:
    """
    Orchestrate an Arena mode run:
    1. Fan-out to all SOTA models in parallel
    2. Stream each response as it arrives
    3. Synthesize a final verdict from all responses
    """
    from config import settings
    from sqlmodel import select

    # Load debate data
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        prompt = debate.prompt
        config = debate.config or {}
        user_id = debate.user_id
        locale = config.get("locale")
        run_attempt = debate.run_attempt or 1

    # Get arena models (filtered to enabled providers)
    arena_models = get_arena_models()
    if not arena_models:
        raise ValueError("No arena models available. Configure at least one provider API key.")

    backend = get_sse_backend()
    usage = UsageAccumulator()

    # Load responses with checkpoint safety
    perspectives_input = {
        "prompt": prompt,
        "models": [m.id for m in arena_models]
    }

    async def load_perspectives_fn(session):
        stmt = select(Message).where(Message.debate_id == debate_id).where(Message.role == "arena_response")
        result = await session.execute(stmt)
        existing = result.scalars().all()
        return [
            ArenaModelResponse(
                model_id=msg.meta.get("model_id") if msg.meta else "",
                display_name=msg.persona,
                provider=msg.meta.get("provider") if msg.meta else "",
                content=msg.content,
                success=msg.meta.get("success", True) if msg.meta else True,
                logo_url=msg.meta.get("logo_url") if msg.meta else None,
                persona_type=msg.meta.get("persona_type") if msg.meta else None,
                persona_tagline=msg.meta.get("persona_tagline") if msg.meta else None,
                error=msg.meta.get("error") if msg.meta else None,
                error_code=msg.meta.get("error_code") if msg.meta else None,
                response_id=msg.meta.get("response_id") if msg.meta else str(msg.id),
                run_attempt=int(msg.meta.get("run_attempt", 1) or 1) if msg.meta else 1,
                retry_generation=int(msg.meta.get("retry_generation", 0) or 0) if msg.meta else 0,
            )
            for msg in existing
        ]

    async def run_perspectives_fn():
        # Notify start
        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "arena_started",
                "debate_id": str(debate_id),
                "models": [
                    {
                        "model_id": m.id,
                        "display_name": m.display_name,
                        "provider": m.provider,
                        "logo_url": m.logo_url,
                        "persona_type": m.persona_type,
                        "persona_tagline": m.persona_tagline,
                    }
                    for m in arena_models
                ],
            },
        )

        # Build locale instruction if set
        _locale_instruction = ""
        if locale and locale != "en":
            _locale_instruction = f"\nIMPORTANT: Respond in the '{locale}' language.\n"

        async def _call_model(model_info, response_id: str, deadline: float, timing: dict | None = None):
            """Call a single SOTA model and return its response.

            Uses streaming when available: publishes model_response_delta events
            via SSE as tokens arrive, then persists the final response.
            """
            if timing is not None:
                timing["start_ts"] = time.monotonic()
            from config import settings as _settings
            stream_enabled = getattr(_settings, "STREAMING_RESPONSES_ENABLED", True)
            timeout_seconds = getattr(_settings, "ARENA_MODEL_TIMEOUT_SECONDS", 45)

            def remaining_timeout() -> float:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                return min(float(timeout_seconds), remaining)

            system_prompt = get_compiled_model_prompt(
                model_display_name=model_info.display_name,
                provider_name=model_info.provider.capitalize(),
                locale=locale,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            if stream_enabled:
                # Streaming path: publish deltas via SSE
                seq_counter = {"seq": 0}

                async def on_delta(delta):
                    seq_counter["seq"] += 1
                    if timing is not None and timing.get("first_delta_ts") is None:
                        timing["first_delta_ts"] = time.monotonic()
                    if timing is not None:
                        timing["delta_count"] = timing.get("delta_count", 0) + 1
                    await backend.publish(
                        f"debate:{debate_id}",
                        {
                            "type": "model_response_delta",
                            "response_id": response_id,
                            "model_id": model_info.id,
                            "display_name": model_info.display_name,
                            "text": delta.text,
                            "delta_sequence": delta.sequence,
                            "accumulated_chars": delta.accumulated_chars,
                            "run_attempt": run_attempt,
                            "retry_generation": 0,
                        },
                    )

                try:
                    from model_gateway import route_llm_stream
                    arena_max = getattr(_settings, "ARENA_MAX_TOKENS", 1200)

                    # A3: Per-model timeout for streaming path
                    try:
                        result = await asyncio.wait_for(
                            route_llm_stream(
                                messages=messages,
                                model_id=model_info.litellm_model or model_info.id,
                                temperature=0.7,
                                max_tokens=arena_max,
                                on_delta=on_delta,
                                debate_id=debate_id,
                                user_id=user_id,
                            ),
                            timeout=remaining_timeout(),
                        )
                    except asyncio.TimeoutError:
                        raise RuntimeError(
                            f"Model {model_info.display_name} timed out after {timeout_seconds} seconds."
                        ) from None

                    if result.success:
                        return ArenaModelResponse(
                            model_id=model_info.id,
                            display_name=model_info.display_name,
                            provider=model_info.provider,
                            content=result.content,
                            success=True,
                            logo_url=model_info.logo_url,
                            persona_type=model_info.persona_type,
                            persona_tagline=model_info.persona_tagline,
                        ), None
                    else:
                        # Streaming returned failure — try non-streaming fallback
                        # within the same timeout window before giving up.
                        logger.warning(
                            f"Streaming failed for {model_info.display_name}: "
                            f"{result.error_message}. Attempting non-streaming fallback."
                        )
                        try:
                            arena_max_fb = getattr(_settings, "ARENA_MAX_TOKENS", 1200)
                            fallback_content, fallback_usage = await asyncio.wait_for(
                                call_llm_for_role(
                                    messages,
                                    role=f"Arena:{model_info.display_name}",
                                    temperature=0.7,
                                    max_tokens=arena_max_fb,
                                    model_override=model_info.litellm_model,
                                    debate_id=debate_id,
                                    extra_tags={"mode": "arena", "arena_model": model_info.id},
                                ),
                                timeout=remaining_timeout(),
                            )
                            return ArenaModelResponse(
                                model_id=model_info.id,
                                display_name=model_info.display_name,
                                provider=model_info.provider,
                                content=fallback_content,
                                success=True,
                                logo_url=model_info.logo_url,
                                persona_type=model_info.persona_type,
                                persona_tagline=model_info.persona_tagline,
                            ), fallback_usage
                        except Exception as fb_exc:
                            logger.warning(
                                f"Non-streaming fallback also failed for "
                                f"{model_info.display_name}: {fb_exc}"
                            )
                            # Convert to failed ArenaModelResponse — do NOT raise
                            err_msg = result.error_message or str(fb_exc)
                            err_code = result.error_code or "stream_and_fallback_failed"
                            from llm_errors import classify_provider_exception
                            failure = classify_provider_exception(fb_exc)
                            return ArenaModelResponse(
                                model_id=model_info.id,
                                display_name=model_info.display_name,
                                provider=model_info.provider,
                                content=f"⚠️ This model failed to respond: {failure.message}",
                                success=False,
                                logo_url=model_info.logo_url,
                                persona_type=model_info.persona_type,
                                persona_tagline=model_info.persona_tagline,
                                error=err_msg,
                                error_code=failure.code.value,
                            ), None
                except Exception:
                    raise

            # Non-streaming fallback
            try:
                arena_max = getattr(settings, "ARENA_MAX_TOKENS", 1200)

                # A4: Per-model timeout for non-streaming path
                try:
                    content, call_usage = await asyncio.wait_for(
                        call_llm_for_role(
                            messages,
                            role=f"Arena:{model_info.display_name}",
                            temperature=0.7,
                            max_tokens=arena_max,
                            model_override=model_info.litellm_model,
                            debate_id=debate_id,
                            extra_tags={"mode": "arena", "arena_model": model_info.id},
                        ),
                        timeout=remaining_timeout(),
                    )
                except asyncio.TimeoutError:
                    raise RuntimeError(
                        f"Model {model_info.display_name} timed out after {timeout_seconds} seconds."
                    ) from None

                return ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=content,
                    success=True,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                ), call_usage
            except Exception as e:
                logger.error(f"Arena model {model_info.id} failed: {e}")

                from llm_errors import ProviderFailureCode, classify_provider_exception
                failure = classify_provider_exception(e)
                err_code = failure.code.value
                friendly_message = failure.message

                if err_code == ProviderFailureCode.INVALID_CREDENTIALS.value:
                    friendly_message = "⚠️ This model provider configuration is invalid (invalid credentials)."
                elif err_code == ProviderFailureCode.INSUFFICIENT_BALANCE.value:
                    friendly_message = "⚠️ This model provider has run out of credits."
                elif err_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
                    friendly_message = "⚠️ Rate limit exceeded for this model provider. Please try again in 1 minute."
                elif err_code == ProviderFailureCode.MODEL_TIMEOUT.value:
                    friendly_message = "⚠️ The model provider request timed out."
                elif err_code == ProviderFailureCode.API_ERROR.value:
                    friendly_message = "⚠️ The model provider API returned an error."
                else:
                    friendly_message = f"⚠️ This model failed to respond: {failure.message}"

                return ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=friendly_message,
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                    error=str(e),
                    error_code=err_code,
                ), None

        # A5: Persist/publish each model response as it completes (not after all finish).
        # Uses asyncio.as_completed so fast models become visible immediately.
        async def _call_and_persist(model_info):
            """Call a model and persist/publish its response immediately.

            Contract: this function NEVER raises. Provider/model errors are
            converted into ArenaModelResponse(success=False) and persisted.
            """
            _timing: dict = {}
            retry_generation = 0
            response_id = (
                f"resp-{debate_id}-"
                f"a{run_attempt}-"
                f"g{retry_generation}-"
                f"{model_info.id}-"
                f"{uuid.uuid4().hex[:12]}"
            )
            lifecycle_payload = {
                "response_id": response_id,
                "model_id": model_info.id,
                "display_name": model_info.display_name,
                "provider": model_info.provider,
                "run_attempt": run_attempt,
                "retry_generation": retry_generation,
            }
            from config import settings as _settings
            total_timeout = float(getattr(_settings, "ARENA_MODEL_TOTAL_TIMEOUT_S", 60))
            deadline = asyncio.get_running_loop().time() + total_timeout
            for event_type in (
                "model_response_queued",
                "model_response_connecting",
                "model_response_started",
            ):
                await backend.publish(
                    f"debate:{debate_id}",
                    {"type": event_type, **lifecycle_payload},
                )

            try:
                async with asyncio.timeout_at(deadline):
                    result = await _call_model(model_info, response_id, deadline, _timing)
                response, call_usage = result
            except Exception as exc:
                logger.error(f"Arena model task exception for {model_info.id}: {exc}")

                from llm_errors import ProviderFailureCode, classify_provider_exception
                failure = classify_provider_exception(exc)
                err_code = failure.code.value
                friendly_message = failure.message

                if err_code == ProviderFailureCode.INVALID_CREDENTIALS.value:
                    friendly_message = "⚠️ This model provider configuration is invalid (invalid credentials)."
                elif err_code == ProviderFailureCode.INSUFFICIENT_BALANCE.value:
                    friendly_message = "⚠️ This model provider has run out of credits."
                elif err_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
                    friendly_message = "⚠️ Rate limit exceeded for this model provider. Please try again in 1 minute."
                elif err_code == ProviderFailureCode.MODEL_TIMEOUT.value:
                    friendly_message = "⚠️ The model provider request timed out."
                elif err_code == ProviderFailureCode.API_ERROR.value:
                    friendly_message = "⚠️ The model provider API returned an error."
                else:
                    friendly_message = f"⚠️ This model encountered an error: {failure.message}"

                response = ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=friendly_message,
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                    error=str(exc),
                    error_code=err_code,
                )
                call_usage = None

            response.response_id = response_id
            response.run_attempt = run_attempt
            response.retry_generation = retry_generation

            await backend.publish(
                f"debate:{debate_id}",
                {"type": "model_response_persisting", **lifecycle_payload},
            )

            # Persist before the terminal lifecycle event. A completed event
            # therefore guarantees that the canonical response can be fetched.
            async with async_session_scope() as session:
                await persist_and_publish_arena_response(session, backend, debate_id, response)

            terminal_payload = {
                "type": "model_response_completed" if response.success else "model_response_failed",
                **lifecycle_payload,
            }
            if not response.success:
                terminal_payload.update(
                    {
                        "error": (response.error or "Model failed to respond")[:200],
                        "error_code": response.error_code,
                    }
                )
            await backend.publish(f"debate:{debate_id}", terminal_payload)

            if PROMETHEUS_AVAILABLE and _timing.get("start_ts"):
                _provider = model_info.provider
                _family = _derive_model_family(model_info)
                _now = time.monotonic()
                _total_sec = _now - _timing["start_ts"]
                record_model_latency(_provider, _family, response.success, _total_sec)
                _first = _timing.get("first_delta_ts")
                if _first:
                    _ttft_sec = _first - _timing["start_ts"]
                    record_ttft(_provider, _family, _ttft_sec)
                    record_connect_latency(_provider, _family, _ttft_sec)
                    _stream_dur = _now - _first
                    _dps = _timing.get("delta_count", 0) / _stream_dur if _stream_dur > 0 else 0
                    record_stream_duration(_provider, "success" if response.success else "failure", _stream_dur)
                    record_stream_dps(_provider, _dps)

            return response, call_usage

        # Fan-out: call all models, collect as each completes
        tasks = [
            asyncio.create_task(_call_and_persist(model))
            for model in arena_models
        ]
        responses = []
        try:
            for task in asyncio.as_completed(tasks):
                response, call_usage = await task
                responses.append(response)
                if call_usage:
                    usage.add_call(call_usage)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        # Sort responses back to original arena_models order
        order_map = {m.id: i for i, m in enumerate(arena_models)}
        responses.sort(key=lambda r: order_map.get(r.model_id, 999))

        # A6: Synthesis trigger policy — keep synthesis after all model calls settle.
        # TODO: Early synthesis when MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS is reached
        # while slow models continue should be a separate product decision.
        return responses

    from orchestration.checkpoints import run_with_checkpoint
    model_responses = await run_with_checkpoint(
        debate_id,
        "arena_perspectives",
        perspectives_input,
        run_perspectives_fn,
        load_perspectives_fn,
        owner_id=execution_owner_id,
        lease_epoch=lease_epoch,
    )

    # Check if we have enough successful responses for synthesis
    successful = [r for r in model_responses if r.success]
    min_required = getattr(settings, "MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS", MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS)
    if len(successful) < min_required:
        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "debate_failed",
                "debate_id": str(debate_id),
                "reason": "all_models_failed",
            },
        )
        return ArenaResult(
            final_answer="All models failed to respond. Please try again.",
            final_meta={"mode": "arena", "error": "all_models_failed"},
            usage_tracker=usage,
            status="failed",
            error_reason="all_models_failed",
            model_responses=model_responses,
        )

    # Staged execution pause check
    if settings.STAGED_DECISION_PIPELINE and not continue_pipeline:
        # Update debate status to perspectives_ready in DB
        async with async_session_scope() as session:
            db_debate = await session.get(Debate, debate_id)
            if db_debate:
                db_debate.status = "perspectives_ready"
                session.add(db_debate)
                await session.commit()

        # Publish early pause event
        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "perspectives_ready",
                "debate_id": str(debate_id),
            },
        )
        return ArenaResult(
            final_answer="Perspectives collected. Synthesis paused.",
            final_meta={
                "mode": "arena",
                "models": [
                    {
                        "model_id": r.model_id,
                        "display_name": r.display_name,
                        "provider": r.provider,
                        "success": r.success,
                        "logo_url": r.logo_url,
                        "persona_type": r.persona_type,
                        "persona_tagline": r.persona_tagline,
                    }
                    for r in model_responses
                ],
                "successful_count": len(successful),
                "total_count": len(model_responses),
                "usage": usage.snapshot(),
            },
            usage_tracker=usage,
            status="perspectives_ready",
            model_responses=model_responses,
        )

    # Synthesize final verdict
    synthesis_input = {
        "prompt": prompt,
        "responses": [r.content for r in model_responses if r.success]
    }

    async def load_synthesis_fn(session):
        stmt = select(Message).where(Message.debate_id == debate_id).where(Message.role == "arena_synthesis")
        result = await session.execute(stmt)
        msg = result.scalars().first()
        if msg:
            sreport = msg.meta.get("synthesis_report") if msg.meta else None
            meta = {
                "synthesis_status": "succeeded" if msg.meta and msg.meta.get("synthesis_success") else "failed",
                "synthesis_error": msg.meta.get("synthesis_error") if msg.meta else None,
                "fallback_model": msg.meta.get("fallback_model") if msg.meta else None,
                "fallback_reason": msg.meta.get("fallback_reason") if msg.meta else None,
                "fallback_response": msg.meta.get("fallback_response") if msg.meta else None,
                "semantic_analysis": msg.meta.get("semantic_analysis") if msg.meta else None,
                "divergence_breakdown": msg.meta.get("divergence_breakdown") if msg.meta else None,
            }
            return msg.content, sreport, meta
        return "Synthesis unavailable.", None, {}

    async def run_synthesis_fn():
        scontent, sreport, meta = await _synthesize_verdict(
            debate_id=debate_id,
            prompt=prompt,
            model_responses=successful,
            usage=usage,
            model_id=model_id,
            locale=locale,
            execution_owner_id=execution_owner_id,
            lease_epoch=lease_epoch,
        )
        ssuccess = meta.get("synthesis_status") == "succeeded"

        # Persist synthesis
        async with async_session_scope() as session:
            session.add(
                Message(
                    debate_id=debate_id,
                    round_index=2,
                    role="arena_synthesis",
                    persona="Synthesizer",
                    content=scontent,
                    meta={
                        "mode": "arena",
                        "phase": "synthesis",
                        "synthesis_success": ssuccess,
                        "synthesis_report": sreport,
                        **meta
                    },
                )
            )
            await session.commit()
        return scontent, sreport, meta

    synthesis_content, synthesis_report, meta_updates = await run_with_checkpoint(
        debate_id,
        "arena_synthesis",
        synthesis_input,
        run_synthesis_fn,
        load_synthesis_fn,
        owner_id=execution_owner_id,
        lease_epoch=lease_epoch,
    )
    synthesis_success = meta_updates.get("synthesis_status") == "succeeded"

    # Build final meta
    failed_models = [r for r in model_responses if not r.success]
    model_warnings = [
        {
            "model_id": r.model_id,
            "display_name": r.display_name,
            "provider": r.provider,
            "error": r.error or "Unknown error",
        }
        for r in failed_models
    ]

    final_meta = {
        "mode": "arena",
        "models": [
            {
                "model_id": r.model_id,
                "display_name": r.display_name,
                "provider": r.provider,
                "success": r.success,
                "logo_url": r.logo_url,
                "persona_type": r.persona_type,
                "persona_tagline": r.persona_tagline,
            }
            for r in model_responses
        ],
        "successful_count": len(successful),
        "total_count": len(model_responses),
        "synthesis_success": synthesis_success,
        "synthesis_report": synthesis_report,
        "model_warnings": model_warnings,
        "usage": usage.snapshot(),
        **meta_updates,
    }

    return ArenaResult(
        final_answer=synthesis_content,
        final_meta=final_meta,
        usage_tracker=usage,
        status="completed",
        model_responses=model_responses,
    )



def sanitize_synthesis_error(error_msg: str) -> str:
    """Sanitize synthesis errors to avoid exposing sensitive details, stack traces, API keys, or provider internals."""
    if not error_msg:
        return "An unknown error occurred during synthesis."
    
    # Redact common key/token patterns
    error_msg = re.sub(r"sk-[a-zA-Z0-9\-_]{12,}", "[REDACTED_API_KEY]", error_msg)
    error_msg = re.sub(r"Bearer\s+[a-zA-Z0-9\-_.]+", "Bearer [REDACTED]", error_msg, flags=re.IGNORECASE)
    
    sensitive_words = [
        "litellm", "openai", "anthropic", "gemini", "google", "cohere", "groq", 
        "together", "ollama", "api_key", "api-key", "credential", "secret", "token",
        "auth", "unauthorized", "forbidden", "rate_limit", "rate-limit", "quota", 
        "billing", "invalid_request", "bad_request", "json.decoder", "json_parse", 
        "parse_error", "traceback", "stack_trace", "line ", "file ", "exception", 
        "connection", "timeout", "status_code", "400", "401", "403", "429", "500"
    ]
    
    msg_lower = error_msg.lower()
    for word in sensitive_words:
        if word in msg_lower:
            return "The structured synthesis service encountered a validation or parsing error. Raw model responses have been preserved."
            
    if len(error_msg) > 120 or "\n" in error_msg:
        return "The structured synthesis service encountered a validation or parsing error. Raw model responses have been preserved."
        
    return error_msg


async def _synthesize_verdict(
    *,
    debate_id: str,
    prompt: str,
    model_responses: List[ArenaModelResponse],
    usage: UsageAccumulator,
    model_id: str | None = None,
    locale: str | None = None,
    execution_owner_id: str | None = None,
    lease_epoch: int | None = None,
) -> tuple[str, dict | None, dict]:
    """Produce the final synthesized verdict and structured decision report from all model responses."""
    from reporting.synthesizer import StructuredSynthesisError, generate_decision_report

    responses_list = [
        {
            "persona": r.display_name,
            "content": r.content
        }
        for r in model_responses
    ]

    try:
        report = await generate_decision_report(
            prompt=prompt,
            responses=responses_list,
            debate_id=debate_id,
            locale=locale,
            model_override=model_id,
            usage=usage,
            execution_owner_id=execution_owner_id,
            lease_epoch=lease_epoch,
        )
        meta_updates = {
            "synthesis_status": "succeeded",
            "synthesis_error": None,
            "fallback_model": None,
            "fallback_reason": None,
            "fallback_response": None,
            "semantic_analysis": report.divergence_breakdown,
            "divergence_breakdown": report.divergence_breakdown,
        }
        return report.executive_summary or report.title, report.model_dump(), meta_updates
    except StructuredSynthesisError as e:
        logger.error(f"Arena synthesis failed with StructuredSynthesisError: {e}")
        successful_responses = [r for r in model_responses if r.success]
        if successful_responses:
            fallback_resp = successful_responses[0]
            fallback_model_name = f"{fallback_resp.display_name} ({fallback_resp.provider.capitalize() if fallback_resp.provider else ''})"
            fallback_content = (
                f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
                f"**{fallback_resp.display_name}:**\n{fallback_resp.content}"
            )
        else:
            fallback_model_name = "Synthesizer"
            fallback_content = "⚠️ Synthesis unavailable. All model calls failed."
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": fallback_content,
            },
            "semantic_analysis": e.semantic_analysis,
            "divergence_breakdown": e.semantic_analysis,
        }
        return fallback_content, None, meta_updates
    except Exception as e:
        logger.error(f"Arena synthesis failed with general exception: {e}")
        successful_responses = [r for r in model_responses if r.success]
        if successful_responses:
            fallback_resp = successful_responses[0]
            fallback_model_name = f"{fallback_resp.display_name} ({fallback_resp.provider.capitalize() if fallback_resp.provider else ''})"
            fallback_content = (
                f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
                f"**{fallback_resp.display_name}:**\n{fallback_resp.content}"
            )
        else:
            fallback_model_name = "Synthesizer"
            fallback_content = "⚠️ Synthesis unavailable. All model calls failed."
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": fallback_content,
            },
            "semantic_analysis": None,
            "divergence_breakdown": None,
        }
        return fallback_content, None, meta_updates
