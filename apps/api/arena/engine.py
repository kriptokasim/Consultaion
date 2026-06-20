"""Arena mode engine: fan-out to SOTA models, collect answers, synthesize verdict."""

from __future__ import annotations

import asyncio
import logging
import re
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

logger = logging.getLogger(__name__)

MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1


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
        if msg.meta and msg.meta.get("model_id") == response.model_id:
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
                    "provider": response.provider,
                    "mode": "arena",
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
            "display_name": response.display_name,
            "provider": response.provider,
            "content": response.content,
            "logo_url": response.logo_url,
            "persona_type": response.persona_type,
            "persona_tagline": response.persona_tagline,
            "success": response.success,
            "error": response.error or (None if response.success else "Model failed to respond"),
            "error_code": response.error_code,
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
        locale_instruction = ""
        if locale and locale != "en":
            locale_instruction = f"\nIMPORTANT: Respond in the '{locale}' language.\n"

        async def _call_model(model_info):
            """Call a single SOTA model and return its response.

            Uses streaming when available: publishes model_response_delta events
            via SSE as tokens arrive, then persists the final response.
            """
            from config import settings as _settings
            stream_enabled = getattr(_settings, "STREAMING_RESPONSES_ENABLED", False)

            system_prompt = get_compiled_model_prompt(
                model_display_name=model_info.display_name,
                provider_name=model_info.provider.capitalize(),
                locale=locale,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            response_id = f"resp-{debate_id}-{model_info.id}"

            if stream_enabled:
                # Streaming path: publish deltas via SSE
                seq_counter = {"seq": 0}

                async def on_delta(delta):
                    seq_counter["seq"] += 1
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
                        },
                    )

                try:
                    await backend.publish(
                        f"debate:{debate_id}",
                        {
                            "type": "model_response_connecting",
                            "response_id": response_id,
                            "model_id": model_info.id,
                            "display_name": model_info.display_name,
                        },
                    )
                    await backend.publish(
                        f"debate:{debate_id}",
                        {
                            "type": "model_response_started",
                            "response_id": response_id,
                            "model_id": model_info.id,
                            "display_name": model_info.display_name,
                        },
                    )

                    from model_gateway import route_llm_stream
                    arena_max = getattr(_settings, "ARENA_MAX_TOKENS", 1200)
                    result = await route_llm_stream(
                        messages=messages,
                        model_id=model_info.litellm_model or model_info.id,
                        temperature=0.7,
                        max_tokens=arena_max,
                        on_delta=on_delta,
                        debate_id=debate_id,
                    )

                    await backend.publish(
                        f"debate:{debate_id}",
                        {
                            "type": "model_response_persisting",
                            "response_id": response_id,
                            "model_id": model_info.id,
                        },
                    )

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
                        raise Exception(result.error_message or "Stream call failed")
                except Exception as e:
                    await backend.publish(
                        f"debate:{debate_id}",
                        {
                            "type": "model_response_failed",
                            "response_id": response_id,
                            "model_id": model_info.id,
                            "display_name": model_info.display_name,
                            "error": str(e)[:200],
                        },
                    )
                    raise

            # Non-streaming fallback
            try:
                arena_max = getattr(settings, "ARENA_MAX_TOKENS", 1200)
                content, call_usage = await call_llm_for_role(
                    messages,
                    role=f"Arena:{model_info.display_name}",
                    temperature=0.7,
                    max_tokens=arena_max,
                    model_override=model_info.litellm_model,
                    debate_id=debate_id,
                    extra_tags={"mode": "arena", "arena_model": model_info.id},
                )
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
                err_code = "unknown"
                if hasattr(e, "error_code"):
                    err_code = e.error_code

                from llm_errors import ProviderFailureCode, classify_provider_exception
                classified_code = classify_provider_exception(e)
                if classified_code:
                    err_code = classified_code.value

                friendly_message = f"⚠️ This model failed to respond: {e}"
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

        # Fan-out: call all models in parallel
        results = await asyncio.gather(
            *[_call_model(m) for m in arena_models],
            return_exceptions=True,
        )

        responses = []
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Arena model task exception: {result}")
                model_info = arena_models[i]
                
                err_code = "unknown"
                from llm_errors import ProviderFailureCode, classify_provider_exception
                classified_code = classify_provider_exception(result)
                if classified_code:
                    err_code = classified_code.value
                    
                friendly_message = f"⚠️ This model encountered an error: {result}"
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

                response = ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=friendly_message,
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                    error=str(result),
                    error_code=err_code,
                )
                responses.append(response)
                async with async_session_scope() as session:
                    await persist_and_publish_arena_response(session, backend, debate_id, response)
                continue

            response, call_usage = result
            responses.append(response)

            if call_usage:
                usage.add_call(call_usage)

            async with async_session_scope() as session:
                await persist_and_publish_arena_response(session, backend, debate_id, response)
        return responses

    from orchestration.checkpoints import run_with_checkpoint
    model_responses = await run_with_checkpoint(
        debate_id,
        "arena_perspectives",
        perspectives_input,
        run_perspectives_fn,
        load_perspectives_fn
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
        load_synthesis_fn
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


