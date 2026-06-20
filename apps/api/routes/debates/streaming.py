import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from auth import get_current_user, get_optional_user
from channels import debate_channel_id
from config import settings
from deps import get_session, get_sse_backend
from exceptions import (
    AppError,
    NotFoundError,
)
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from models import Debate, Message, PairwiseVote, Score, User
from schemas import DebateConfig, default_debate_config
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend

from routes.common import (
    is_debate_public,
    require_debate_access,
    track_metric,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    start_time = time.time()
    
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)

    from services.schema_capabilities import get_registry, get_schema_capabilities
    caps = get_schema_capabilities(session, get_registry())

    messages: list[Message] = []
    scores: list[Score] = []
    pairwise_votes: list[PairwiseVote] = []

    if caps.has_message_table:
        try:
            messages = session.exec(
                select(Message).where(Message.debate_id == debate_id).order_by(sa.asc(Message.created_at))
            ).all()
        except Exception as exc:
            logger.warning("events_messages_failed debate_id=%s error=%s", debate_id, exc)

    if caps.has_score_table:
        try:
            scores = session.exec(
                select(Score).where(Score.debate_id == debate_id).order_by(sa.asc(Score.created_at))
            ).all()
        except Exception as exc:
            logger.warning("events_scores_failed debate_id=%s error=%s", debate_id, exc)

    if caps.has_pairwise_vote_table:
        try:
            pairwise_votes = session.exec(
                select(PairwiseVote)
                .where(PairwiseVote.debate_id == debate_id)
                .order_by(sa.asc(PairwiseVote.created_at))
            ).all()
        except Exception as exc:
            logger.warning("events_pairwise_failed debate_id=%s error=%s", debate_id, exc)

    events: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "seat":
            meta = message.meta or {}
            events.append(
                {
                    "type": "seat_message",
                    "round": message.round_index,
                    "seat_id": meta.get("seat_id"),
                    "seat_name": message.persona,
                    "role": meta.get("role_profile") or "agent",
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "text": message.content,
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "delegate":
            # Conversation mode messages stored as 'delegate'
            meta = message.meta or {}
            events.append(
                {
                    "type": "seat_message",
                    "round": message.round_index,
                    "seat_id": meta.get("seat_id"),
                    "seat_name": message.persona,
                    "role": "agent",
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "text": message.content,
                    "mode": "conversation",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "arena_response":
            meta = message.meta or {}
            events.append(
                {
                    "type": "arena_response",
                    "round": message.round_index,
                    "model_id": meta.get("model_id"),
                    "display_name": message.persona,
                    "provider": meta.get("provider"),
                    "content": message.content,
                    "logo_url": meta.get("logo_url"),
                    "persona_type": meta.get("persona_type"),
                    "persona_tagline": meta.get("persona_tagline"),
                    "success": meta.get("success", True),
                    "mode": "arena",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "arena_synthesis":
            events.append(
                {
                    "type": "arena_synthesis",
                    "round": message.round_index,
                    "actor": "Synthesizer",
                    "role": "synthesizer",
                    "text": message.content,
                    "mode": "arena",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role in {"candidate", "revised"}:
            events.append(
                {
                    "type": "message",
                    "round": message.round_index,
                    "actor": message.persona,
                    "role": "agent",
                    "text": message.content,
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )

    for score in scores:
        events.append(
            {
                "type": "score",
                "persona": score.persona,
                "judge": score.judge,
                "score": float(score.score),
                "rationale": score.rationale,
                "role": "judge",
                "at": score.created_at.isoformat(),
            }
        )

    for vote in pairwise_votes:
        if vote.winner == "A":
            winner = vote.candidate_a
            loser = vote.candidate_b
        elif vote.winner == "B":
            winner = vote.candidate_b
            loser = vote.candidate_a
        else:
            winner = vote.winner
            loser = vote.candidate_b if winner == vote.candidate_a else vote.candidate_a
        events.append(
            {
                "type": "pairwise",
                "judge_id": vote.judge_id,
                "candidate_a": vote.candidate_a,
                "candidate_b": vote.candidate_b,
                "winner": winner,
                "loser": loser,
                "at": vote.created_at.isoformat(),
            }
        )

    if debate.final_content:
        events.append(
            {
                "type": "final",
                "actor": "Synthesizer",
                "role": "synthesizer",
                "text": debate.final_content,
                "at": debate.updated_at.isoformat() if debate.updated_at else None,
            }
        )

    events.sort(key=lambda e: e.get("at") or "")
    
    elapsed_ms = (time.time() - start_time) * 1000
    if elapsed_ms > 500:
        logger.warning(f"timeline_fetch_slow: debate_id={debate_id} elapsed_ms={elapsed_ms:.1f} events={len(events)}")

    # Filter events for unauthenticated public users — strip internal metadata
    if not current_user and is_debate_public(debate):
        from serializers import serialize_events_public
        return {"items": serialize_events_public(events)}

    return {"items": events}


@router.get("/debates/{debate_id}/responses")
@router.get("/api/v1/debates/{debate_id}/responses")
async def get_debate_responses(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Canonical persisted model responses (PR-FH89).

    Independent of timeline / events / scores. Returns the persisted
    Message rows for a debate normalized into a single DTO. A database
    failure becomes a non-2xx response — never a successful empty list.
    """
    from services.debate_responses import (
        ResponsesQueryError,
        fetch_persisted_responses,
    )

    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    public_view = (not current_user) and is_debate_public(debate)

    try:
        payload = fetch_persisted_responses(session, debate, is_public=public_view)
    except ResponsesQueryError as exc:
        logger.error("persisted_responses_query_failed debate_id=%s error=%s", debate_id, exc)
        raise AppError(
            message="Failed to read persisted model responses.",
            code="debate.responses_query_failed",
        ) from exc

    return payload


@router.get("/debates/{debate_id}/judges")
async def get_debate_judges(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    judges = [{"name": judge.name, "type": getattr(judge, "type", "judge")} for judge in config.judges]
    return {"judges": judges}


@router.get("/debates/{debate_id}/scores.csv")
async def export_scores_csv(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    
    # Check export quota BEFORE doing expensive work (Patchset 65.B1)
    from billing.service import check_export_quota
    check_export_quota(session, current_user.id)
    
    scores = session.exec(select(Score).where(Score.debate_id == debate_id).order_by(sa.asc(Score.created_at))).all()
    if not scores:
        raise NotFoundError(message="No scores found", code="scores.not_found")

    from billing.service import increment_export_usage
    from services.reporting import generate_csv_content
    loop = asyncio.get_running_loop()
    content = await loop.run_in_executor(None, lambda: generate_csv_content(scores))
    
    # Increment and commit after successful generation
    increment_export_usage(session, current_user.id)
    from usage_limits import increment_export_usage_daily
    increment_export_usage_daily(session, current_user.id)
    session.commit()
    
    filename = f"scores_{debate_id}.csv"
    from audit import record_audit
    record_audit(
        "export_scores_csv",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        session=session,
    )
    from fastapi import Response
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/debates/{debate_id}/replay")
async def replay_events(
    debate_id: str,
    from_sequence: Optional[int] = Query(default=None, description="Start sequence offset (non-inclusive)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    """Retrieve cached real-time events from the memory/Redis event log."""
    require_debate_access(session.get(Debate, debate_id), current_user, session)
    channel_id = debate_channel_id(debate_id)
    
    events = await sse_backend.replay(channel_id, after_sequence=from_sequence)
            
    return {"events": events}


@router.get("/debates/{debate_id}/stream")
async def stream_events(
    debate_id: str,
    request: Request,
    last_sequence: Optional[int] = Query(default=None, description="Last sequence number received by client"),
    session: Session = Depends(get_session),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Cookie/Bearer auth only — no query JWT for first-party flow
    from auth import get_optional_user
    user = get_optional_user(request=request, session=session)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="authentication required")

    require_debate_access(session.get(Debate, debate_id), user, session)
    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)

    # Resolve reconnect cursor BEFORE any code reads it.
    # Precedence: query parameter → Last-Event-ID header → None
    last_seq_val: int | None = last_sequence
    if last_seq_val is None:
        last_event_id = request.headers.get("last-event-id")
        if last_event_id:
            try:
                last_seq_val = int(last_event_id)
            except (TypeError, ValueError):
                track_metric("sse_invalid_last_event_id")
                last_seq_val = None

    # Reject negative sequence values
    if last_seq_val is not None and last_seq_val < 0:
        last_seq_val = None

    # Record metrics after cursor is resolved
    track_metric("sse_stream_open")
    if last_seq_val is not None:
        from observability.metrics import record_sse_reconnect
        record_sse_reconnect()

    # Acquire lease-based concurrent stream slot
    from sse_backend import StreamLeaseResult, get_stream_lease_manager
    lease_mgr = get_stream_lease_manager()
    subscriber_id = f"{user.id}:{uuid.uuid4().hex}"
    lease_result = await lease_mgr.try_acquire(debate_id, subscriber_id)
    if lease_result in (StreamLeaseResult.DENIED, StreamLeaseResult.ERROR_FAIL_CLOSED):
        active = await lease_mgr.active_count(debate_id)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=f"Too many concurrent streams for debate {debate_id} ({active} active)",
            headers={"Retry-After": "30"},
        )

    async def eventgen():
        # Use exactly-once lease context manager
        from metrics import increment_metric
        from sse_backend import acquired_stream_lease, get_stream_lease_manager

        lease_mgr = get_stream_lease_manager()

        async with acquired_stream_lease(lease_mgr, debate_id, subscriber_id):
            # Periodically check if client disconnected to forcefully release lease
            async def check_disconnect(task: asyncio.Task):
                while True:
                    if await request.is_disconnected():
                        task.cancel()
                        break
                    await asyncio.sleep(2)

            monitor_task = asyncio.create_task(check_disconnect(asyncio.current_task()))
            try:
                async for event in sse_backend.subscribe(channel_id, last_sequence=last_seq_val):
                    # Skip heartbeat events from being serialized to the client
                    # Heartbeats are used internally for silence detection
                    evt_type = event.get("type")
                    payload = event.get("payload")
                    payload_type = payload.get("type") if isinstance(payload, dict) else None
                    if evt_type == "heartbeat" or payload_type == "heartbeat":
                        increment_metric("sse.heartbeat.emitted")
                        continue

                    seq = event.get("sequence")
                    id_prefix = f"id: {seq}\n" if seq is not None else ""
                    yield f"{id_prefix}data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # Check either top-level or payload type
                    if evt_type == "final" or payload_type == "final":
                        break
            finally:
                # Cancel and await monitor task
                monitor_task.cancel()
                from contextlib import suppress
                with suppress(asyncio.CancelledError):
                    await monitor_task

    # Explicit CORS headers — CORSMiddleware does not reliably inject on streaming responses
    allowed_origin = settings.WEB_APP_ORIGIN or "*"
    return StreamingResponse(
        eventgen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )
