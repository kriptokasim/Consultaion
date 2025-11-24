from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from sqlmodel import Session, select

from models import Debate, Message
from parliament.schemas import TimelineEvent


def build_debate_timeline(session: Session, debate: Debate) -> List[TimelineEvent]:
    """Build a normalized timeline suitable for replay."""
    events: list[TimelineEvent] = []

    # 1. Initial System Notice
    events.append(
        TimelineEvent(
            debate_id=debate.id,
            event_id=f"system:init:{debate.id}",
            ts=debate.created_at or datetime.now(timezone.utc),
            type="system_notice",
            content=f"Debate initialized: {debate.prompt}",
            meta={"topic": debate.prompt},
        )
    )

    # 2. Process Messages
    rows = session.exec(
        select(Message).where(Message.debate_id == debate.id).order_by(Message.created_at.asc())
    ).all()

    current_round = -1
    
    for row in rows:
        ts = row.created_at or datetime.now(timezone.utc)
        meta = row.meta or {}
        round_idx = meta.get("round_index") or row.round_index or 0
        
        # Emit round start if needed
        if round_idx > current_round:
            # Close previous round if any (simplified logic, assumes sequential rounds)
            if current_round >= 0:
                 events.append(
                    TimelineEvent(
                        debate_id=debate.id,
                        event_id=f"round:{current_round}:end",
                        ts=ts, # Approximate end time as start of next event
                        type="round_end",
                        round_index=current_round,
                        content=f"Round {current_round + 1} ended",
                    )
                )
            
            events.append(
                TimelineEvent(
                    debate_id=debate.id,
                    event_id=f"round:{round_idx}:start",
                    ts=ts,
                    type="round_start",
                    round_index=round_idx,
                    content=f"Round {round_idx + 1} started",
                )
            )
            current_round = round_idx

        # Seat Messages
        if row.role == "seat":
            seat_id = meta.get("seat_id") or row.persona or "unknown"
            events.append(
                TimelineEvent(
                    debate_id=debate.id,
                    event_id=f"msg:{row.id}",
                    ts=ts,
                    type="seat_message",
                    round_index=round_idx,
                    seat_id=str(seat_id),
                    seat_label=row.persona, # Use persona name as label
                    role=meta.get("role_profile") or row.role,
                    provider=meta.get("provider"),
                    model=meta.get("model"),
                    stance=meta.get("stance"),
                    content=row.content,
                    meta=meta,
                )
            )
        # System/Notice Messages (if stored as messages)
        elif row.role == "system":
             events.append(
                TimelineEvent(
                    debate_id=debate.id,
                    event_id=f"sys:{row.id}",
                    ts=ts,
                    type="system_notice",
                    content=row.content,
                    meta=meta,
                )
            )

    # Close final round
    if current_round >= 0:
        events.append(
            TimelineEvent(
                debate_id=debate.id,
                event_id=f"round:{current_round}:end",
                ts=datetime.now(timezone.utc), # Use current time or last msg time
                type="round_end",
                round_index=current_round,
                content=f"Round {current_round + 1} ended",
            )
        )

    # 3. Terminal Event
    status = (debate.status or "").lower()
    if status == "failed":
        failure_reason = None
        if isinstance(debate.final_meta, dict):
            failure_reason = (debate.final_meta.get("failure") or {}).get("reason") or debate.final_meta.get("error")
        
        events.append(
            TimelineEvent(
                debate_id=debate.id,
                event_id=f"system:failed:{debate.id}",
                ts=debate.updated_at or datetime.now(timezone.utc),
                type="debate_failed",
                content="Debate failed",
                meta={"reason": failure_reason} if failure_reason else {},
            )
        )
    elif status == "completed":
        events.append(
            TimelineEvent(
                debate_id=debate.id,
                event_id=f"system:completed:{debate.id}",
                ts=debate.updated_at or datetime.now(timezone.utc),
                type="debate_completed",
                content="Debate completed successfully",
            )
        )

    # Ensure all timestamps are timezone-aware
    for event in events:
        if event.ts.tzinfo is None:
            event.ts = event.ts.replace(tzinfo=timezone.utc)

    events.sort(key=lambda e: e.ts)
    return events
