from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents import UsageAccumulator, call_llm_for_role
from database_async import async_session_scope
from models import Debate, Message
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)

async def run_compare_debate(
    debate_id: str,
) -> Any:
    """
    Orchestrate a side-by-side compare mode run.
    """
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        prompt = debate.prompt
        config = debate.config or {}
        compare_models = config.get("compare_models", [])
        user_id = debate.user_id

    if not compare_models:
        compare_models = [debate.model_id] if debate.model_id else []

    backend = get_sse_backend()
    usage = UsageAccumulator()
    
    await backend.publish(
        f"debate:{debate_id}",
        {"type": "round_started", "debate_id": str(debate_id), "round": 1, "phase": "compare"}
    )

    async def _run_model(model_id: str):
        # We need to resolve provider names for display if available
        display_name = model_id.split("/")[-1]
        
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. Answer the user's prompt clearly and directly."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            content, call_usage = await call_llm_for_role(
                messages,
                role=display_name,
                temperature=0.7, # standard temp
                model_id=model_id,
                debate_id=debate_id,
                extra_tags={"mode": "compare"},
            )
            return {
                "model_id": model_id,
                "display_name": display_name,
                "content": content,
                "usage": call_usage,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error in compare run for model {model_id}: {e}")
            return {
                "model_id": model_id,
                "display_name": display_name,
                "content": f"Failed to generate response: {e}",
                "usage": None,
                "success": False,
            }

    results = await asyncio.gather(*[_run_model(mid) for mid in compare_models])
    
    final_contents = []
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
                    "mode": "compare"
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
                "mode": "compare"
            }
        )
        final_contents.append(f"### {res['display_name']}\n{res['content']}\n")

    final_meta = {
        "models": compare_models,
        "usage": usage.snapshot(),
        "mode": "compare",
    }
    
    joined_content = "\n\n---\n\n".join(final_contents)

    class CompareResult:
        def __init__(self, answer, meta, usg, status, err):
            self.final_answer = answer
            self.final_meta = meta
            self.usage_tracker = usg
            self.status = status
            self.error_reason = err

    return CompareResult(
        answer=joined_content,
        meta=final_meta,
        usg=usage,
        status="completed",
        err=None
    )
