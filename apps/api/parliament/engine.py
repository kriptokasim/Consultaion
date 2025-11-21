from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agents import UsageAccumulator, call_llm_for_role, UsageCall
from database import session_scope
from models import Debate, Message
from schemas import PanelConfig, PanelSeat, default_panel_config
from sse_backend import get_sse_backend

from .prompts import build_messages_for_seat, transcript_to_text, PARLIAMENT_CHARTER
from .roles import ROLE_PROFILES


DEFAULT_ROUNDS: List[dict[str, str]] = [
    {"index": 1, "phase": "explore", "task_for_seat": "Share your strongest arguments, opportunities, or risks."},
    {"index": 2, "phase": "rebuttal", "task_for_seat": "Respond to concerns raised by other seats. Strengthen or challenge prior claims."},
    {"index": 3, "phase": "converge", "task_for_seat": "Converge on recommendations, clear risks, and success criteria."},
]


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


@dataclass
class ParliamentResult:
    final_answer: str
    final_meta: dict[str, Any]
    usage_tracker: UsageAccumulator


async def run_parliament_debate(
    debate: Debate,
    *,
    model_id: str | None,
) -> ParliamentResult:
    panel_payload = debate.panel_config or default_panel_config().model_dump()
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
            f"debate:{debate.id}",
            {
                "type": "round_started",
                "debate_id": str(debate.id),
                "round": round_info["index"],
                "phase": round_info["phase"],
            },
        )
        round_turns = await _execute_round(
            debate=debate,
            panel=panel,
            round_info=round_info,
            transcript_summary=transcript_to_text(transcript_buffer),
            usage_tracker=usage,
        )
        for turn in round_turns:
            event = {
                "type": "seat_message",
                "debate_id": str(debate.id),
                "round": turn.round_index,
                "phase": turn.phase,
                "seat_id": turn.seat_id,
                "seat_name": turn.seat_name,
                "provider": turn.provider,
                "model": turn.model,
                "content": turn.content,
            }
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
            await backend.publish(f"debate:{debate.id}", event)
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

    final_text, final_usage = await _synthesize_verdict(
        debate=debate,
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
    debate: Debate,
    panel: PanelConfig,
    round_info: dict[str, Any],
    transcript_summary: str,
    usage_tracker: UsageAccumulator,
) -> List[SeatTurn]:
    turns: list[SeatTurn] = []
    for seat in panel.seats:
        role_profile = ROLE_PROFILES.get(seat.role_profile)
        seat_role = role_profile.title if role_profile else seat.role_profile
        messages = build_messages_for_seat(
            debate=debate,
            seat=seat.model_dump(),
            round_info=round_info,
            transcript=transcript_summary,
        )
        text, call_usage = await call_llm_for_role(
            messages,
            role=seat.display_name,
            temperature=seat.temperature or 0.5,
            model_override=seat.model,
            model_id=debate.model_id,
            debate_id=debate.id,
        )
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
                content=text,
                usage=call_usage,
            )
        )
        with session_scope() as session:
            session.add(
                Message(
                    debate_id=debate.id,
                    round_index=round_info["index"],
                    role="seat",
                    persona=seat.display_name,
                    content=text,
                    meta={
                        "seat_id": seat.seat_id,
                        "role_profile": seat.role_profile,
                        "provider": seat.provider_key,
                        "model": seat.model,
                        "phase": round_info["phase"],
                    },
                )
            )
    return turns


async def _synthesize_verdict(
    *,
    debate: Debate,
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
                f"Debate prompt:\n{debate.prompt}\n\nPanel seats: {seats_summary}\n\n"
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
        debate_id=debate.id,
    )
