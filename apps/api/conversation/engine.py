from __future__ import annotations

import logging
from typing import Any, List

from agents import UsageAccumulator, call_llm_for_role
from database import session_scope
from integrations.langfuse import update_trace_metadata
from models import Debate, DebateAttempt, Message
from orchestration.execution_context import require_current_execution_lease
from orchestration.execution_lease import ExecutionSupersededError
from orchestration.fencing import assert_execution_ownership_sync
from prompts.conversation import (
    CONVERSATION_SCRIBE_PROMPT,
    CONVERSATION_SYNTHESIS_PROMPT,
    CONVERSATION_SYSTEM_PROMPT,
)
from schemas import PanelConfig, default_panel_config
from sqlalchemy import select
from sse_backend import get_sse_backend

from config import settings

logger = logging.getLogger(__name__)

async def run_conversation_debate(
    debate_id: str,
    *,
    model_id: str | None,
) -> Any:
    """
    Orchestrate a collaborative conversation mode run.

    Message writes are fenced on execution-lease ownership and carry an
    attempt-scoped ``response_id`` so duplicate dispatches cannot create
    duplicates. Run status is deterministic: zero successful seat
    contributions fails the run instead of reporting a fabricated result.
    """
    lease = require_current_execution_lease()
    # Load debate data synchronously to avoid detached objects
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")

        # Eager load/copy fields needed
        prompt = debate.prompt
        panel_payload = debate.panel_config or default_panel_config().model_dump()

    # Load config
    try:
        panel = PanelConfig.model_validate(panel_payload)
    except Exception:
        panel = default_panel_config()

    backend = get_sse_backend()
    usage = UsageAccumulator()
    transcript: List[dict] = []
    total_seat_failures = 0

    # Configuration
    num_rounds = settings.CONVERSATION_MAX_ROUNDS
    max_tokens = settings.CONVERSATION_MAX_TOTAL_TOKENS
    truncated = False
    truncate_reason = None

    # Notify start
    await backend.publish(
        f"debate:{debate_id}",
        {"type": "round_started", "debate_id": str(debate_id), "round": 0, "phase": "conversation_start"}
    )

    for round_idx in range(1, num_rounds + 1):
        # Check token limits
        if usage.total_tokens >= max_tokens:
            truncated = True
            truncate_reason = "token_limit"
            logger.info(f"Conversation {debate_id} truncated due to token limit ({usage.total_tokens} >= {max_tokens})")
            break

        # Notify round start
        await backend.publish(
            f"debate:{debate_id}",
            {"type": "round_started", "debate_id": str(debate_id), "round": round_idx, "phase": "discussion"}
        )

        round_messages = []

        for seat in panel.seats:
            # Build context from transcript
            context_text = "\n".join([f"{t['seat']}: {t['content']}" for t in transcript])

            messages = [
                {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Topic: {prompt}\n\nPrevious discussion:\n{context_text}\n\nYour contribution:"
                }
            ]

            try:
                content, call_usage = await call_llm_for_role(
                    messages,
                    role=seat.display_name,
                    temperature=seat.temperature or 0.7,
                    model_override=seat.model,
                    model_id=model_id,
                    debate_id=debate_id,
                    extra_tags={"mode": "conversation", "round": round_idx},
                )
                usage.add_call(call_usage)

                # Persist message (fenced + idempotent per attempt/round/seat)
                response_id = (
                    f"conversation:{debate_id}:a{lease.run_attempt}"
                    f":r{round_idx}:{seat.seat_id}"
                )
                with session_scope() as session:
                    assert_execution_ownership_sync(session, lease)
                    attempt_id = session.execute(
                        select(DebateAttempt.id).where(
                            DebateAttempt.debate_id == debate_id,
                            DebateAttempt.attempt_number == lease.run_attempt,
                        )
                    ).scalar_one_or_none()
                    existing = session.exec(
                        select(Message).where(
                            Message.debate_id == debate_id,
                            Message.response_id == response_id,
                        )
                    ).first()
                    if existing is None:
                        session.add(
                            Message(
                                debate_id=debate_id,
                                attempt_id=attempt_id,
                                response_id=response_id,
                                round_index=round_idx,
                                role="delegate",
                                persona=seat.display_name,
                                content=content,
                                meta={
                                    "seat_id": seat.seat_id,
                                    "model": seat.model,
                                    "mode": "conversation",
                                    "run_attempt": lease.run_attempt,
                                }
                            )
                        )

                # Update transcript
                transcript.append({"seat": seat.display_name, "content": content})
                round_messages.append({"seat": seat.display_name, "content": content})

                # Emit event
                await backend.publish(
                    f"debate:{debate_id}",
                    {
                        "type": "seat_message", # Reusing seat_message for compatibility
                        "debate_id": str(debate_id),
                        "round": round_idx,
                        "seat_name": seat.display_name,
                        "content": content,
                        "mode": "conversation",
                        "response_id": response_id,
                    }
                )

            except ExecutionSupersededError:
                # Ownership lost: this is NOT a seat failure. Stop the entire
                # run immediately — no further seats, rounds, scribe, synthesis,
                # events, or paid provider work. The new owner owns the run.
                raise
            except Exception as e:
                logger.error(f"Error in conversation round {round_idx} for seat {seat.display_name}: {e}")
                total_seat_failures += 1
                continue

        # Scribe Summary
        summary_messages = [
            {"role": "system", "content": CONVERSATION_SCRIBE_PROMPT},
            {"role": "user", "content": f"Topic: {prompt}\n\nRound {round_idx} Transcript:\n" + "\n".join([f"{m['seat']}: {m['content']}" for m in round_messages])}
        ]

        try:
            summary_content, summary_usage = await call_llm_for_role(
                summary_messages,
                role="Scribe",
                temperature=0.3,
                model_id=model_id,
                debate_id=debate_id,
                extra_tags={"mode": "conversation", "round": round_idx},
            )
            usage.add_call(summary_usage)

            await backend.publish(
                f"debate:{debate_id}",
                {
                    "type": "conversation_summary",
                    "debate_id": str(debate_id),
                    "round": round_idx,
                    "content": summary_content
                }
            )
        except Exception as e:
            logger.error(f"Error generating summary for round {round_idx}: {e}")

    # Final Synthesis
    synthesis_messages = [
        {"role": "system", "content": CONVERSATION_SYNTHESIS_PROMPT},
        {"role": "user", "content": f"Topic: {prompt}\n\nFull Transcript:\n" + "\n".join([f"{t['seat']}: {t['content']}" for t in transcript])}
    ]

    final_content = ""
    try:
        final_content, final_usage = await call_llm_for_role(
            synthesis_messages,
            role="Facilitator",
            temperature=0.4,
            model_id=model_id,
            debate_id=debate_id,
            extra_tags={"mode": "conversation", "phase": "synthesis"},
        )
        usage.add_call(final_usage)
    except Exception as e:
        logger.error(f"Error generating final synthesis: {e}")
        final_content = "Failed to generate synthesis."

    final_meta = {
        "rounds": num_rounds,
        "transcript_count": len(transcript),
        "usage": usage.snapshot(),
        "mode": "conversation",
        "truncated": truncated,
        "truncate_reason": truncate_reason,
        "run_attempt": lease.run_attempt,
    }

    class _ConversationResult:
        def __init__(self, answer, meta, usg, status, err):
            self.final_answer = answer
            self.final_meta = meta
            self.usage_tracker = usg
            self.status = status
            self.error_reason = err

    # Deterministic terminal semantics: no successful seat contribution at all
    # is a failed run — never fabricate a completed result from an empty transcript.
    if not transcript:
        final_meta["total_seat_failures"] = total_seat_failures
        return _ConversationResult(
            answer="",
            meta=final_meta,
            usg=usage,
            status="failed",
            err="all_conversation_seats_failed",
        )

    synthesis_failed = final_content == "Failed to generate synthesis."
    if synthesis_failed:
        # Do not present the internal failure string as a model verdict.
        final_content = "\n\n".join(
            [f"**{t['seat']}**: {t['content']}" for t in transcript]
        )
        final_meta["synthesis_failed"] = True

    if total_seat_failures:
        final_meta["total_seat_failures"] = total_seat_failures

    # Update trace metadata
    update_trace_metadata({
        "conversation.rounds_total": num_rounds,
        "conversation.rounds_completed": round_idx if not truncated else round_idx - 1, # Approx
        "conversation.transcript_count": len(transcript),
        "conversation.truncated": truncated,
        "conversation.truncate_reason": truncate_reason,
        "conversation.mode": "conversation"
    })

    # Do not increment the daily token counter here. Every gateway call reserves
    # and settles its own token usage before/after provider work, and terminal
    # accounting applies only any remaining aggregate delta. Re-applying the full
    # Conversation total here would double-charge quota for the same tokens.

    status = "completed"
    err = None
    if synthesis_failed or total_seat_failures:
        status = "completed_with_warnings"
        err = "conversation_partial_failure"

    return _ConversationResult(
        answer=final_content,
        meta=final_meta,
        usg=usage,
        status=status,
        err=err,
    )
