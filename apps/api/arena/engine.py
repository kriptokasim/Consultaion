from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents import UsageAccumulator, call_llm_for_role
from database_async import async_session_scope
from models import Debate, Message
from sse_backend import get_sse_backend
from parliament.model_registry import get_model_info

logger = logging.getLogger(__name__)

async def run_arena_debate(debate_id: str) -> Any:
    """
    Orchestrate an arena mode run.
    Runs the prompt against 4 specific models, then synthesizes the best answer using Claude.
    """
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        prompt = debate.prompt
        # User id not strictly needed for this simple implementation but good to have
        user_id = debate.user_id

    backend = get_sse_backend()
    usage = UsageAccumulator()

    await backend.publish(
        f"debate:{debate_id}",
        {"type": "round_started", "debate_id": str(debate_id), "round": 1, "phase": "arena_generation"}
    )

    arena_models = [
        "gpt4o-deep",
        "claude-sonnet",
        "gemini-2-5-pro",
        "deepseek-chat"
    ]

    async def _run_model(model_id: str):
        model_info = get_model_info(model_id)
        display_name = model_info.display_name if model_info else model_id

        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. Answer the user's prompt clearly and directly."},
            {"role": "user", "content": prompt}
        ]

        try:
            content, call_usage = await call_llm_for_role(
                messages,
                role=display_name,
                temperature=0.7,
                model_id=model_id,
                debate_id=debate_id,
                extra_tags={"mode": "arena"},
            )
            return {
                "model_id": model_id,
                "display_name": display_name,
                "content": content,
                "usage": call_usage,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error in arena run for model {model_id}: {e}")
            return {
                "model_id": model_id,
                "display_name": display_name,
                "content": f"Failed to generate response: {e}",
                "usage": None,
                "success": False,
            }

    results = await asyncio.gather(*[_run_model(mid) for mid in arena_models])

    final_contents = []
    responses_for_synthesis = []

    for res in results:
        if res["usage"]:
            usage.add_call(res["usage"])

        async with async_session_scope() as session:
            msg = Message(
                debate_id=debate_id,
                round_index=1,
                role="seat",
                persona=res["display_name"],
                content=res["content"],
                meta={
                    "seat_id": res["model_id"],
                    "model": res["model_id"],
                    "mode": "arena"
                }
            )
            session.add(msg)
            await session.commit()

        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "seat_message",
                "debate_id": debate_id,
                "round": 1,
                "seat_name": res["display_name"],
                "seat_id": res["model_id"],
                "content": res["content"],
                "model": res["model_id"],
                "mode": "arena"
            }
        )
        responses_for_synthesis.append(f"Answer from {res['display_name']}:\n{res['content']}\n")
        final_contents.append(f"### {res['display_name']}\n{res['content']}\n")

    # Synthesis Step
    await backend.publish(
        f"debate:{debate_id}",
        {"type": "round_started", "debate_id": str(debate_id), "round": 2, "phase": "arena_synthesis"}
    )

    synthesis_model = "claude-sonnet"
    synthesis_model_info = get_model_info(synthesis_model)
    synthesis_display_name = "Synthesizer (Claude 3.5 Sonnet)"

    synthesis_prompt = f"""You are an expert synthesizer. You are given a user prompt and {len(arena_models)} different answers from top AI models.
Your task is to synthesize these answers into a single, comprehensive, and highly accurate final answer.
Extract the strong points from each model's answer, resolve any contradictions, and present the information clearly.

User Prompt:
{prompt}

{chr(10).join(responses_for_synthesis)}

Please provide the final synthesized answer below.
"""

    synthesis_messages = [
        {"role": "system", "content": "You are a master synthesizer that combines the best parts of multiple AI answers."},
        {"role": "user", "content": synthesis_prompt}
    ]

    try:
        synth_content, synth_usage = await call_llm_for_role(
            synthesis_messages,
            role=synthesis_display_name,
            temperature=0.5,
            model_id=synthesis_model,
            debate_id=debate_id,
            extra_tags={"mode": "arena", "phase": "synthesis"},
        )
        if synth_usage:
            usage.add_call(synth_usage)
    except Exception as e:
        logger.error(f"Error in arena synthesis run: {e}")
        synth_content = f"Failed to generate synthesis: {e}"

    async with async_session_scope() as session:
        msg = Message(
            debate_id=debate_id,
            round_index=2,
            role="synthesizer",
            persona=synthesis_display_name,
            content=synth_content,
            meta={
                "seat_id": "synthesizer",
                "model": synthesis_model,
                "mode": "arena"
            }
        )
        session.add(msg)
        await session.commit()

    await backend.publish(
        f"debate:{debate_id}",
        {
            "type": "seat_message",
            "debate_id": debate_id,
            "round": 2,
            "seat_name": synthesis_display_name,
            "seat_id": "synthesizer",
            "content": synth_content,
            "model": synthesis_model,
            "mode": "arena"
        }
    )

    final_meta = {
        "models": arena_models,
        "synthesis_model": synthesis_model,
        "usage": usage.snapshot(),
        "mode": "arena",
    }

    # Also prepend synthesis to final content for fallback cases
    joined_content = f"### Final Synthesized Answer\n{synth_content}\n\n---\n\n" + "\n\n---\n\n".join(final_contents)

    class ArenaResult:
        def __init__(self, answer, meta, usg, status, err):
            self.final_answer = answer
            self.final_meta = meta
            self.usage_tracker = usg
            self.status = status
            self.error_reason = err

    return ArenaResult(
        answer=joined_content,
        meta=final_meta,
        usg=usage,
        status="completed",
        err=None
    )