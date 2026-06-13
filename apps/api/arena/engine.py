"""Arena mode engine: fan-out to SOTA models, collect answers, synthesize verdict."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List

from agents import UsageAccumulator, call_llm_for_role
from arena.prompts import ARENA_MODEL_SYSTEM_PROMPT, ARENA_SYNTHESIS_PROMPT
from database_async import async_session_scope
from models import Debate, Message
from parliament.model_registry import get_arena_models
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)


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
    from sqlmodel import select
    from config import settings

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

    # Load existing responses if resuming/continuing
    existing_messages = []
    async with async_session_scope() as session:
        stmt = select(Message).where(Message.debate_id == debate_id).where(Message.role == "arena_response")
        result = await session.execute(stmt)
        existing_messages = result.scalars().all()

    model_responses: List[ArenaModelResponse] = []
    if existing_messages:
        model_responses = [
            ArenaModelResponse(
                model_id=msg.meta.get("model_id") if msg.meta else "",
                display_name=msg.persona,
                provider=msg.meta.get("provider") if msg.meta else "",
                content=msg.content,
                success=msg.meta.get("success", True) if msg.meta else True,
                logo_url=msg.meta.get("logo_url") if msg.meta else None,
                persona_type=msg.meta.get("persona_type") if msg.meta else None,
                persona_tagline=msg.meta.get("persona_tagline") if msg.meta else None,
            )
            for msg in existing_messages
        ]
        logger.info("Resuming arena %s: loaded %d existing responses", debate_id, len(model_responses))
    else:
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
            """Call a single SOTA model and return its response."""
            system_prompt = ARENA_MODEL_SYSTEM_PROMPT.format(
                model_display_name=model_info.display_name,
                provider_name=model_info.provider.capitalize(),
            ) + locale_instruction

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            try:
                content, call_usage = await call_llm_for_role(
                    messages,
                    role=f"Arena:{model_info.display_name}",
                    temperature=0.7,
                    max_tokens=1200,
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
                return ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=f"⚠️ This model failed to respond: {e}",
                    success=False,
                    logo_url=model_info.logo_url,
                    persona_type=model_info.persona_type,
                    persona_tagline=model_info.persona_tagline,
                ), None

        # Fan-out: call all models in parallel
        results = await asyncio.gather(
            *[_call_model(m) for m in arena_models],
            return_exceptions=True,
        )

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Arena model task exception: {result}")
                model_info = arena_models[i]
                response = ArenaModelResponse(
                    model_id=model_info.id,
                    display_name=model_info.display_name,
                    provider=model_info.provider,
                    content=f"⚠️ This model encountered an error.",
                    success=False,
                    logo_url=model_info.logo_url,
                )
                model_responses.append(response)
                continue

            response, call_usage = result
            model_responses.append(response)

            if call_usage:
                usage.add_call(call_usage)

            # Persist message
            async with async_session_scope() as session:
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
                        },
                    )
                )
                await session.commit()

            # Stream response event
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
                },
            )

    # Check if we have any successful responses
    successful = [r for r in model_responses if r.success]
    if not successful:
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
    synthesis_content, synthesis_report, meta_updates = await _synthesize_verdict(
        debate_id=debate_id,
        prompt=prompt,
        model_responses=successful,
        usage=usage,
        model_id=model_id,
        locale=locale,
    )
    synthesis_success = meta_updates.get("synthesis_status") == "succeeded"

    # Persist synthesis
    async with async_session_scope() as session:
        session.add(
            Message(
                debate_id=debate_id,
                round_index=2,
                role="arena_synthesis",
                persona="Synthesizer",
                content=synthesis_content,
                meta={"mode": "arena", "phase": "synthesis", "synthesis_success": synthesis_success},
            )
        )
        await session.commit()

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


import re

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
    from reporting.synthesizer import generate_decision_report, StructuredSynthesisError

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
        fallback_model_name = f"{model_responses[0].display_name} ({model_responses[0].provider.capitalize() if model_responses[0].provider else ''})"
        fallback_content = (
            f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
            f"**{model_responses[0].display_name}:**\n{model_responses[0].content}"
        )
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": model_responses[0].content,
            },
            "semantic_analysis": e.semantic_analysis,
            "divergence_breakdown": e.semantic_analysis,
        }
        return fallback_content, None, meta_updates
    except Exception as e:
        logger.error(f"Arena synthesis failed with general exception: {e}")
        fallback_model_name = f"{model_responses[0].display_name} ({model_responses[0].provider.capitalize() if model_responses[0].provider else ''})"
        fallback_content = (
            f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
            f"**{model_responses[0].display_name}:**\n{model_responses[0].content}"
        )
        meta_updates = {
            "synthesis_status": "failed",
            "synthesis_error": sanitize_synthesis_error(str(e)),
            "fallback_model": fallback_model_name,
            "fallback_reason": "Top model response shown because structured synthesis failed",
            "fallback_response": {
                "model": fallback_model_name,
                "content": model_responses[0].content,
            },
            "semantic_analysis": None,
            "divergence_breakdown": None,
        }
        return fallback_content, None, meta_updates


