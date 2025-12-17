from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from agents import UsageAccumulator, UsageCall, call_llm_for_role
from config import settings
from database import session_scope
from models import Debate, Message
from pydantic import ValidationError
from schemas import PanelConfig, default_panel_config
from sse_backend import get_sse_backend

from .config import PARLIAMENT_CHARTER
from .prompts import build_messages_for_seat, transcript_to_text
from .roles import ROLE_PROFILES
from .schemas import DebateSnapshot, SeatLLMEnvelope, SeatMessage

logger = logging.getLogger(__name__)

from .config import DEFAULT_ROUNDS


@dataclass
class SeatTurn:
    seat_id: str
    seat_name: str
    role_profile: str
    round_index: int
    phase: str
    provider: str
    model: str
    content: str
    usage: UsageCall
    stance: Optional[str] = None
    reasoning: Optional[str] = None


@dataclass
class ParliamentResult:
    final_answer: str
    final_meta: dict[str, Any]
    usage_tracker: UsageAccumulator
    status: str = "completed"
    error_reason: str | None = None


@dataclass
class RoundOutcome:
    status: str
    round_index: int
    reason: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0


def parse_seat_llm_output(raw_text: str) -> SeatLLMEnvelope:
    try:
        data = json.loads(raw_text)
        return SeatLLMEnvelope.model_validate(data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        logger.warning("Seat LLM output was not valid JSON; falling back to raw content: %s", exc)
        return SeatLLMEnvelope(content=raw_text.strip()[:16384])


def _resolve_tolerance(panel: PanelConfig) -> tuple[float, int, bool]:
    return (
        panel.max_seat_fail_ratio if panel.max_seat_fail_ratio is not None else settings.DEBATE_MAX_SEAT_FAIL_RATIO,
        panel.min_required_seats if panel.min_required_seats is not None else settings.DEBATE_MIN_REQUIRED_SEATS,
        panel.fail_fast if panel.fail_fast is not None else settings.DEBATE_FAIL_FAST,
    )


def _build_seat_message_event(debate_id: str, turn: SeatTurn) -> dict:
    return {
        "type": "seat_message",
        "debate_id": str(debate_id),
        "round": turn.round_index,
        "phase": turn.phase,
        "seat_id": turn.seat_id,
        "seat_name": turn.seat_name,
        "provider": turn.provider,
        "model": turn.model,
        "content": turn.content,
        "seat": {
            "seat_id": turn.seat_id,
            "role_id": turn.role_profile,
            "provider": turn.provider,
            "model": turn.model,
            "stance": turn.stance,
        },
    }


async def run_parliament_debate(
    debate_id: str,
    *,
    model_id: str | None,
) -> ParliamentResult:
    # Load debate data synchronously to avoid detached objects
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        
        # Eager load/copy fields needed
        prompt = debate.prompt
        panel_payload = debate.panel_config or default_panel_config().model_dump()
        debate_model_id = debate.model_id
    
    try:
        panel = PanelConfig.model_validate(panel_payload)
    except Exception:
        panel = default_panel_config()

    backend = get_sse_backend()
    usage = UsageAccumulator()
    transcript_buffer: list[dict[str, str]] = []
    round_history: list[dict[str, Any]] = []
    seat_usage: list[dict[str, Any]] = []

    for round_info in DEFAULT_ROUNDS:
        await backend.publish(
            f"debate:{debate_id}",
            {
                "type": "round_started",
                "debate_id": str(debate_id),
                "round": round_info["index"],
                "phase": round_info["phase"],
            },
        )
        outcome, round_turns = await _execute_round(
            debate_id=debate_id,
            prompt=prompt,
            debate_model_id=debate_model_id,
            panel=panel,
            round_info=round_info,
            transcript_summary=transcript_to_text(transcript_buffer),
            usage_tracker=usage,
        )
        seat_messages: list[SeatMessage] = []
        for turn in round_turns:
            event = _build_seat_message_event(debate_id, turn)
            transcript_buffer.append({"seat_name": turn.seat_name, "content": turn.content})
            seat_usage.append(
                {
                    "seat_id": turn.seat_id,
                    "seat_name": turn.seat_name,
                    "role_profile": turn.role_profile,
                    "provider": turn.provider,
                    "model": turn.model,
                    "tokens": turn.usage.total_tokens,
                }
            )
            seat_messages.append(
                SeatMessage(
                    seat_id=turn.seat_id,
                    role_id=turn.role_profile,
                    provider=turn.provider,
                    model=turn.model,
                    content=turn.content,
                    reasoning=turn.reasoning,
                    stance=turn.stance,
                    round_index=turn.round_index,
                    created_at=datetime.now(timezone.utc),
                )
            )
            await backend.publish(f"debate:{debate_id}", event)
        _ = DebateSnapshot(
            debate_id=str(debate_id),
            round_index=round_info["index"],
            seat_messages=seat_messages,
        )
        round_history.append(
            {
                "index": round_info["index"],
                "phase": round_info["phase"],
                "seats": [
                    {
                        "seat_id": turn.seat_id,
                        "seat_name": turn.seat_name,
                        "excerpt": turn.content[:400],
                        "model": turn.model,
                        "provider": turn.provider,
                    }
                    for turn in round_turns
                ],
            }
        )
        if outcome.status == "failed":
            await backend.publish(
                f"debate:{debate_id}",
                {
                    "type": "debate_failed",
                    "debate_id": str(debate_id),
                    "reason": outcome.reason or "seat_failure_threshold_exceeded",
                },
            )
            failure_meta = {
                "engine": panel.engine_version,
                "rounds": round_history,
                "panel": panel.model_dump(),
                "seat_usage": seat_usage,
                "usage": usage.snapshot(),
                "failure": {
                    "reason": outcome.reason or "seat_failure_threshold_exceeded",
                    "round_index": outcome.round_index,
                    "success_count": outcome.success_count,
                    "failure_count": outcome.failure_count,
                },
            }
            return ParliamentResult(
                final_answer="",
                final_meta=failure_meta,
                usage_tracker=usage,
                status="failed",
                error_reason=outcome.reason or "seat_failure_threshold_exceeded",
            )

    final_text, final_usage = await _synthesize_verdict(
        debate_id=debate_id,
        prompt=prompt,
        transcript_summary=transcript_to_text(transcript_buffer, limit=24),
        panel=panel,
        model_id=model_id,
    )
    usage.add_call(final_usage)
    seat_usage.append(
        {
            "seat_id": "chair",
            "seat_name": "Chair",
            "role_profile": "chair",
            "provider": final_usage.provider,
            "model": final_usage.model,
            "tokens": final_usage.total_tokens,
        }
    )

    final_meta = {
        "engine": panel.engine_version,
        "rounds": round_history,
        "panel": panel.model_dump(),
        "seat_usage": seat_usage,
        "ranking": [seat.display_name for seat in panel.seats],
        "usage": usage.snapshot(),
    }
    return ParliamentResult(final_answer=final_text, final_meta=final_meta, usage_tracker=usage)


async def _execute_round(
    *,
    debate_id: str,
    prompt: str,
    debate_model_id: str | None,
    panel: PanelConfig,
    round_info: dict[str, Any],
    transcript_summary: str,
    usage_tracker: UsageAccumulator,
) -> tuple[RoundOutcome, List[SeatTurn]]:
    turns: list[SeatTurn] = []
    success_count = 0
    failure_count = 0
    fail_ratio_limit, min_required, fail_fast = _resolve_tolerance(panel)
    for seat in panel.seats:
        role_profile = ROLE_PROFILES.get(seat.role_profile)
        seat_role = role_profile.title if role_profile else seat.role_profile
        try:
            messages = build_messages_for_seat(
                debate_id=debate_id,
                prompt=prompt,
                seat=seat.model_dump(),
                round_info=round_info,
                transcript=transcript_summary,
            )
            text, call_usage = await call_llm_for_role(
                messages,
                role=seat.display_name,
                temperature=seat.temperature or 0.5,
                model_override=seat.model,
                model_id=debate_model_id,
                debate_id=debate_id,
            )
            envelope = parse_seat_llm_output(text)
            usage_tracker.add_call(call_usage)
            turns.append(
                SeatTurn(
                    seat_id=seat.seat_id,
                    seat_name=seat.display_name,
                    role_profile=seat.role_profile,
                    round_index=round_info["index"],
                    phase=round_info["phase"],
                    provider=seat.provider_key,
                    model=seat.model,
                    content=envelope.content,
                    stance=envelope.stance,
                    reasoning=envelope.reasoning,
                    usage=call_usage,
                )
            )
            with session_scope() as session:
                session.add(
                    Message(
                        debate_id=debate_id,
                        round_index=round_info["index"],
                        role="seat",
                        persona=seat.display_name,
                        content=envelope.content,
                        meta={
                            "seat_id": seat.seat_id,
                            "role_profile": seat.role_profile,
                            "provider": seat.provider_key,
                            "model": seat.model,
                            "round_index": round_info["index"],
                            "stance": envelope.stance,
                            "reasoning": envelope.reasoning,
                            "phase": round_info["phase"],
                        },
                    )
                )
            success_count += 1
        except Exception as exc:  # pragma: no cover - counted for tolerance
            logger.error(
                "Seat %s failed in round %s: %s",
                seat.seat_id,
                round_info.get("index"),
                exc,
            )
            failure_count += 1
            continue

    total_seats = len(panel.seats) or (success_count + failure_count)
    fail_ratio = (failure_count / total_seats) if total_seats else 1.0
    outcome_status = "ok"
    outcome_reason: Optional[str] = None
    if fail_fast and (fail_ratio > fail_ratio_limit or success_count < min_required):
        outcome_status = "failed"
        outcome_reason = "seat_failure_threshold_exceeded"

    return RoundOutcome(
        status=outcome_status,
        round_index=round_info["index"],
        reason=outcome_reason,
        success_count=success_count,
        failure_count=failure_count,
    ), turns


async def _synthesize_verdict(
    *,
    debate_id: str,
    prompt: str,
    transcript_summary: str,
    panel: PanelConfig,
    model_id: str | None,
) -> tuple[str, UsageCall]:
    seats_summary = ", ".join(f"{seat.display_name} ({seat.role_profile})" for seat in panel.seats)
    messages = [
        {"role": "system", "content": PARLIAMENT_CHARTER + "\n\nYou are the Parliament Chair preparing the final verdict."},
        {
            "role": "user",
            "content": (
                f"Debate prompt:\n{prompt}\n\nPanel seats: {seats_summary}\n\n"
                f"Transcript summary:\n{transcript_summary}\n\n"
                "Produce a concise verdict that captures consensus recommendations, key risks, and next actions."
            ),
        },
    ]
    chair_model = panel.seats[0].model if panel.seats else None
    return await call_llm_for_role(
        messages,
        role="Chair",
        temperature=0.35,
        model_override=chair_model,
        model_id=model_id,
        debate_id=debate_id,
    )
