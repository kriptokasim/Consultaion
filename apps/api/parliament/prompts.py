from __future__ import annotations

from typing import Any, Iterable

from .config import PARLIAMENT_CHARTER, SEAT_OUTPUT_CONTRACT
from .roles import ROLE_PROFILES


def seat_output_contract_instructions() -> str:
    return SEAT_OUTPUT_CONTRACT


def build_messages_for_seat(
    *,
    debate_id: str,
    prompt: str,
    seat: dict[str, Any],
    round_info: dict[str, Any],
    transcript: str,
    locale: str | None = None,
) -> list[dict[str, str]]:
    role_profile = ROLE_PROFILES.get(seat.get("role_profile")) or ROLE_PROFILES["optimist"]

    parts = [
        PARLIAMENT_CHARTER,
        role_profile.instructions,
        seat_output_contract_instructions(),
    ]

    # Inject language instruction when user's locale is non-English
    LOCALE_NAMES: dict[str, str] = {
        "tr": "Turkish",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "it": "Italian",
        "nl": "Dutch",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "ar": "Arabic",
        "ru": "Russian",
    }
    if locale and locale.lower() not in ("en", "en-us", "en-gb"):
        lang_name = LOCALE_NAMES.get(locale.lower().split("-")[0], locale)
        parts.append(
            f"IMPORTANT: You MUST write your entire response (including the 'content' field in your JSON) in {lang_name}. "
            f"All explanations, arguments, and reasoning must be in {lang_name}. "
            "Only keep JSON keys, field names, and technical terms in English."
        )

    system_content = "\n\n".join(parts)

    seat_name = seat.get("display_name") or seat.get("seat_id") or "Seat"
    user_content = (
        f"Debate ID: {debate_id}\n"
        f"Round: {round_info['index']} ({round_info['phase']})\n\n"
        f"Seat: {seat_name}\n"
        f"User question:\n{prompt}\n\n"
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
