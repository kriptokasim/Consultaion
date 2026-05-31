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
) -> ArenaResult:
    """
    Orchestrate an Arena mode run:
    1. Fan-out to all SOTA models in parallel
    2. Stream each response as it arrives
    3. Synthesize a final verdict from all responses
    """
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
    model_responses: List[ArenaModelResponse] = []

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

    # Synthesize final verdict
    synthesis_content = await _synthesize_verdict(
        debate_id=debate_id,
        prompt=prompt,
        model_responses=successful,
        usage=usage,
        model_id=model_id,
        locale=locale,
    )

    # Persist synthesis
    async with async_session_scope() as session:
        session.add(
            Message(
                debate_id=debate_id,
                round_index=2,
                role="arena_synthesis",
                persona="Synthesizer",
                content=synthesis_content,
                meta={"mode": "arena", "phase": "synthesis"},
            )
        )
        await session.commit()

    # Build final meta
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
        "usage": usage.snapshot(),
    }

    return ArenaResult(
        final_answer=synthesis_content,
        final_meta=final_meta,
        usage_tracker=usage,
        status="completed",
        model_responses=model_responses,
    )


async def _synthesize_verdict(
    *,
    debate_id: str,
    prompt: str,
    model_responses: List[ArenaModelResponse],
    usage: UsageAccumulator,
    model_id: str | None = None,
    locale: str | None = None,
) -> str:
    """Produce the final synthesized verdict from all model responses."""
    # Build the candidate block for synthesis
    candidate_block = "\n\n---\n\n".join(
        f"### {r.display_name} ({r.provider.capitalize()})\n{r.content}"
        for r in model_responses
    )

    system_prompt = ARENA_SYNTHESIS_PROMPT.format(model_count=len(model_responses))
    if locale and locale != "en":
        system_prompt += f"\nIMPORTANT: Produce the final synthesis in the '{locale}' language.\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"**Original Question:**\n{prompt}\n\n**Model Responses:**\n\n{candidate_block}\n\nProduce the final synthesized verdict.",
        },
    ]

    try:
        content, call_usage = await call_llm_for_role(
            messages,
            role="Arena:Synthesizer",
            temperature=0.4,
            max_tokens=1500,
            model_id=model_id,
            debate_id=debate_id,
            extra_tags={"mode": "arena", "phase": "synthesis"},
        )
        usage.add_call(call_usage)
        return content
    except Exception as e:
        logger.error(f"Arena synthesis failed: {e}")
        # Fallback: return the best individual response
        return (
            f"⚠️ Synthesis unavailable. Here is the top response:\n\n"
            f"**{model_responses[0].display_name}:**\n{model_responses[0].content}"
        )
