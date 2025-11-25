from __future__ import annotations

from typing import Any, Iterable

from models import Debate

from .config import PARLIAMENT_CHARTER, SEAT_OUTPUT_CONTRACT
from .roles import ROLE_PROFILES


def seat_output_contract_instructions() -> str:
    return SEAT_OUTPUT_CONTRACT


def build_messages_for_seat(
    *,
    debate: Debate,
    seat: dict[str, Any],
    round_info: dict[str, Any],
    transcript: str,
) -> list[dict[str, str]]:
    role_profile = ROLE_PROFILES.get(seat.get("role_profile")) or ROLE_PROFILES["optimist"]

    system_content = "\n\n".join(
        [
            PARLIAMENT_CHARTER,
            role_profile.instructions,
            seat_output_contract_instructions(),
        ]
    )

    seat_name = seat.get("display_name") or seat.get("seat_id") or "Seat"
    user_content = (
        f"Debate ID: {debate.id}\n"
        f"Round: {round_info['index']} ({round_info['phase']})\n\n"
        f"Seat: {seat_name}\n"
        f"User question:\n{debate.prompt}\n\n"
        f"Summary of previous contributions:\n{transcript or 'No previous contributions.'}\n\n"
        f"Your task this round: {round_info.get('task_for_seat', '').strip() or 'Contribute meaningfully to this round.'}\n\n"
        "Remember: respond with JSON only using the provided schema."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def transcript_to_text(entries: Iterable[dict[str, str]], limit: int = 12) -> str:
    chunks = []
    for entry in list(entries)[-limit:]:
        name = entry.get("seat_name") or entry.get("seat_id") or "Seat"
        content = entry.get("content", "").strip()
        if not content:
            continue
        chunks.append(f"{name}: {content}")
    return "\n".join(chunks) or "No transcript yet."
