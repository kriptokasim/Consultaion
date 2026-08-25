from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents import UsageAccumulator, call_llm_for_role
from database_async import async_session_scope
from llm_errors import classify_provider_exception
from models import Debate, DebateAttempt, Message
from orchestration.execution_context import require_current_execution_lease
from orchestration.execution_lease import ExecutionSupersededError
from orchestration.fencing import assert_execution_ownership
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)

async def run_compare_debate(
    debate_id: str,
) -> Any:
    """
    Orchestrate a side-by-side compare mode run.

    Responses are persisted and published progressively as each model
    finishes (as_completed). Every write is fenced on execution-lease
    ownership; ownership loss raises ExecutionSupersededError and stops the
    run immediately (no further persistence, SSE, or result reporting).
    Durable messages carry both the relational ``attempt_id`` and a
    deterministic attempt-scoped ``response_id`` for idempotency. Provider
    failures are classified into safe codes/messages — raw exception text is
    never persisted or emitted.
    """
    lease = require_current_execution_lease()

    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        prompt = debate.prompt
        config = debate.config or {}
        compare_models = list(config.get("compare_models", []))
        _user_id = debate.user_id

    if not compare_models:
        compare_models = [debate.model_id] if debate.model_id else []

    backend = get_sse_backend()
    usage = UsageAccumulator()
    succeeded = 0
    failed = 0

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
                "error_message": None,
                "error_code": None,
            }
        except Exception as e:
            safe = classify_provider_exception(e)
            logger.error(
                "Compare model %s failed for debate %s: code=%s",
                model_id, debate_id, safe.code.value,
            )
            return {
                "model_id": model_id,
                "display_name": display_name,
                "content": None,
                "usage": None,
                "success": False,
                "error_message": safe.message,
                "error_code": safe.code.value,
            }

    async def _persist_and_publish(res: dict) -> None:
        nonlocal succeeded, failed
        if res["usage"]:
            usage.add_call(res["usage"])

        response_id = f"compare:{debate_id}:a{lease.run_attempt}:{res['model_id']}"

        async with async_session_scope() as session:
            # Awaited async fence: a superseded owner raises here and the
            # exception propagates out of the engine (never swallowed).
            await assert_execution_ownership(session, lease)

            from sqlalchemy import select as _select

            attempt_id = (
                await session.execute(
                    _select(DebateAttempt.id).where(
                        DebateAttempt.debate_id == debate_id,
                        DebateAttempt.attempt_number == lease.run_attempt,
                    )
                )
            ).scalar_one_or_none()

            existing = (
                await session.execute(
                    _select(Message).where(
                        Message.debate_id == debate_id,
                        Message.response_id == response_id,
                    )
                )
            ).first()
            if existing is None:
                session.add(
                    Message(
                        debate_id=debate_id,
                        attempt_id=attempt_id,
                        response_id=response_id,
                        round_index=1,
                        role="seat",
                        persona=res["display_name"],
                        content=res["content"] or "",
                        meta={
                            "seat_id": res["model_id"],
                            "model": res["model_id"],
                            "mode": "compare",
                            "success": res["success"],
                            "error": res["error_message"],
                            "error_code": res["error_code"],
                            "run_attempt": lease.run_attempt,
                        },
                    )
                )
                await session.commit()

        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "seat_message",
                "debate_id": str(debate_id),
                "round": 1,
                "seat_name": res["display_name"],
                "seat_id": res["model_id"],
                "content": res["content"],
                "model": res["model_id"],
                "mode": "compare",
                "response_id": response_id,
                "success": res["success"],
                "error": res["error_message"],
                "error_code": res["error_code"],
            }
        )

        if res["success"]:
            succeeded += 1
        else:
            failed += 1

    tasks = [asyncio.create_task(_run_model(mid)) for mid in compare_models]
    try:
        for coro in asyncio.as_completed(tasks):
            res = await coro
            await _persist_and_publish(res)
    except ExecutionSupersededError:
        # Ownership lost: cancel all in-flight provider work and stop. No
        # final result, no terminal event — the new owner owns the run.
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    final_meta = {
        "models": compare_models,
        "successful_count": succeeded,
        "total_count": len(compare_models),
        "failed_count": failed,
        "usage": usage.snapshot(),
        "mode": "compare",
        "run_attempt": lease.run_attempt,
    }

    class CompareResult:
        def __init__(self, answer, meta, usg, status, err):
            self.final_answer = answer
            self.final_meta = meta
            self.usage_tracker = usg
            self.status = status
            self.error_reason = err

    if succeeded == 0:
        return CompareResult(
            answer="",
            meta=final_meta,
            usg=usage,
            status="failed",
            err="all_compare_models_failed",
        )

    final_contents = []
    async with async_session_scope() as session:
        from sqlalchemy import select as _select
        rows = (
            await session.execute(
                _select(Message)
                .where(
                    Message.debate_id == debate_id,
                    Message.role == "seat",
                    Message.response_id.like(f"compare:{debate_id}:a{lease.run_attempt}:%"),
                )
                .order_by(Message.id.asc())
            )
        ).scalars().all()
        seen: set[str] = set()
        for row in rows:
            if row.response_id in seen or not row.content:
                continue
            seen.add(row.response_id)
            final_contents.append(f"### {row.persona}\n{row.content}\n")

    joined_content = "\n\n---\n\n".join(final_contents)

    status = "completed" if failed == 0 else "completed_with_warnings"
    err = None if failed == 0 else f"{failed}_of_{len(compare_models)}_models_failed"

    return CompareResult(
        answer=joined_content,
        meta=final_meta,
        usg=usage,
        status=status,
        err=err,
    )
