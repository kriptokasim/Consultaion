from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from models import Debate, Message, Score, Vote
from sqlmodel import Session, select

from parliament.schemas import TimelineEvent


def build_debate_timeline(session: Session, debate: Debate) -> List[TimelineEvent]:
    """Build a normalized timeline suitable for replay."""
    events: list[TimelineEvent] = []

    # 1. Fetch all related data
    messages = session.exec(
        select(Message).where(Message.debate_id == debate.id).order_by(Message.created_at.asc())
    ).all()
    
    scores = session.exec(
        select(Score).where(Score.debate_id == debate.id).order_by(Score.created_at.asc())
    ).all()
    
    votes = session.exec(
        select(Vote).where(Vote.debate_id == debate.id).order_by(Vote.created_at.asc())
    ).all()

    # 2. System Init
    events.append(
        TimelineEvent(
            id=f"sys_init_{debate.id}",
            debate_id=debate.id,
            ts=debate.created_at or datetime.now(timezone.utc),
            type="notice",
            round=0,
            payload={
                "message": f"Debate initialized: {debate.prompt}",
                "topic": debate.prompt,
                "level": "info"
            }
        )
    )

    # 3. Process Messages
    # Group by rounds if needed, but here we just map directly
    for msg in messages:
        ts = msg.created_at or datetime.now(timezone.utc)
        meta = msg.meta or {}
        
        # Determine strict type
        evt_type = "message"
        if msg.role == "seat":
            evt_type = "seat_message"
        elif msg.role == "system":
            evt_type = "notice"
            
        payload = {
            "text": msg.content,
            "role": msg.role,
            "persona": msg.persona,
            **meta
        }
        
        # Normalize seat fields
        if evt_type == "seat_message":
            payload["seat_id"] = meta.get("seat_id")
            payload["seat_name"] = msg.persona
        
        events.append(
            TimelineEvent(
                id=f"msg_{msg.id}",
                debate_id=debate.id,
                ts=ts,
                type=evt_type,
                round=msg.round_index,
                seat=msg.persona if msg.role == "seat" else None,
                payload=payload
            )
        )

    # 4. Process Scores
    for score in scores:
        events.append(
            TimelineEvent(
                id=f"score_{score.id}",
                debate_id=debate.id,
                ts=score.created_at,
                type="score",
                round=0, # Scores usually valid for the whole debate or specific round if we tracked it
                seat=score.persona,
                payload={
                    "judge": score.judge,
                    "score": score.score,
                    "rationale": score.rationale,
                    "persona": score.persona
                }
            )
        )

    # 5. Process Votes
    for vote in votes:
        events.append(
            TimelineEvent(
                id=f"vote_{vote.id}",
                debate_id=debate.id,
                ts=vote.created_at,
                type="vote",
                round=0,
                payload={
                    "method": vote.method,
                    "rankings": vote.rankings,
                    "result": vote.result
                }
            )
        )

    # 6. Terminal Event
    status = (debate.status or "").lower()
    if status == "failed":
        failure_meta = debate.final_meta or {}
        events.append(
            TimelineEvent(
                id=f"sys_failed_{debate.id}",
                debate_id=debate.id,
                ts=debate.updated_at or datetime.now(timezone.utc),
                type="error",
                round=0,
                payload={
                    "message": "Debate failed",
                    "reason": failure_meta.get("error") or "Unknown error",
                    **failure_meta
                }
            )
        )
    elif status == "completed":
        events.append(
            TimelineEvent(
                id=f"sys_done_{debate.id}",
                debate_id=debate.id,
                ts=debate.updated_at or datetime.now(timezone.utc),
                type="final",
                round=0,
                payload={
                    "content": debate.final_content or "",
                    "meta": debate.final_meta or {}
                }
            )
        )

    # Ensure timezones
    for event in events:
        if event.ts.tzinfo is None:
            event.ts = event.ts.replace(tzinfo=timezone.utc)

    events.sort(key=lambda e: e.ts)
    return events
