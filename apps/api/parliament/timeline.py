from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from sqlmodel import Session, select

from models import Debate, Message
from parliament.schemas import TimelineEvent


def build_debate_timeline(session: Session, debate: Debate) -> List[TimelineEvent]:
    """Build a normalized timeline suitable for replay."""
    events: list[TimelineEvent] = []

    rows = session.exec(
        select(Message).where(Message.debate_id == debate.id).order_by(Message.created_at.asc())
    ).all()
    for row in rows:
        if not row.created_at:
            ts = datetime.now(timezone.utc)
        else:
            ts = row.created_at
        meta = row.meta or {}
        phase = meta.get("phase") or "draft"
        seat_id = meta.get("seat_id") or row.persona or "unknown"
        role = meta.get("role_profile") or row.role or "seat"
        provider = meta.get("provider")
        model = meta.get("model")
        stance = meta.get("stance")
        reasoning = meta.get("reasoning")
        events.append(
            TimelineEvent(
                ts=ts,
                debate_id=debate.id,
                round_index=meta.get("round_index") or row.round_index or 0,
                phase=str(phase),
                seat_id=str(seat_id),
                seat_role=str(role),
                provider=provider,
                model=model,
                event_type="seat_message" if row.role == "seat" else "system_notice",
                content=row.content,
                stance=stance,
                reasoning=reasoning,
                meta=meta or None,
            )
        )

    if (debate.status or "").lower() == "failed":
        failure_reason = None
        if isinstance(debate.final_meta, dict):
            failure_reason = (debate.final_meta.get("failure") or {}).get("reason") or debate.final_meta.get("error")
        events.append(
            TimelineEvent(
                ts=debate.updated_at or datetime.now(timezone.utc),
                debate_id=debate.id,
                round_index=len(events),
                phase="draft",
                seat_id="system",
                seat_role="system",
                event_type="system_notice",
                content="Debate aborted",
                meta={"failure_reason": failure_reason} if failure_reason else {"failure_reason": "unknown"},
            )
        )

    events.sort(key=lambda e: e.ts)
    return events
