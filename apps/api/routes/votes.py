"""
Patchset 77: Votes API endpoints for Conversation V2.

Provides POST /v1/votes (upsert) and GET /v1/votes/summary.
All endpoints gated by ENABLE_CONVERSATION_V2 feature flag.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from auth import get_current_user, get_optional_user
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query
from models import ConversationVote, Debate, Message, User
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from config import settings
from routes.common import require_debate_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/votes", tags=["votes"])


# -----------------------------------------------------------------------------
# Feature Flag Guard
# -----------------------------------------------------------------------------

def require_conversation_v2():
    """Hard reject if ENABLE_CONVERSATION_V2 is disabled."""
    if not settings.ENABLE_CONVERSATION_V2:
        raise HTTPException(
            status_code=501,
            detail={
                "error": {
                    "code": "feature.disabled",
                    "message": "Conversation V2 is not enabled"
                }
            }
        )


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class VoteCreate(BaseModel):
    """Request to create or update a vote."""
    conversation_id: str = Field(..., description="Conversation/debate ID")
    message_id: str = Field(..., description="Message ID being voted on")
    vote: Literal[-1, 1] = Field(..., description="Vote value: -1 (down), 1 (up)")
    reason: Optional[str] = Field(None, max_length=50, description="Optional structured reason")
    confidence: Optional[int] = Field(None, ge=1, le=3, description="Confidence level 1-3")


class VoteResponse(BaseModel):
    """Response after vote is recorded."""
    success: bool = True
    vote_id: str
    action: str  # "created" or "updated"


class VoteSummary(BaseModel):
    """Aggregated vote summary for a conversation."""
    conversation_id: str
    total_up: int = 0
    total_down: int = 0
    net_score: int = 0
    total_votes: int = 0


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

def _require_vote_target(
    session: Session,
    conversation_id: str,
    message_id: str,
    current_user: Optional[User],
) -> tuple[Debate, Message]:
    debate = require_debate_access(session.get(Debate, conversation_id), current_user, session)
    try:
        message_pk = int(message_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    message = session.get(Message, message_pk)
    if not message or message.debate_id != debate.id:
        raise HTTPException(status_code=404, detail="message not found")
    return debate, message

@router.post("", response_model=VoteResponse)
def create_or_update_vote(
    payload: VoteCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update a vote (upsert behavior).
    
    Idempotent on (conversation_id, message_id, user_id).
    """
    require_conversation_v2()
    
    _require_vote_target(session, payload.conversation_id, payload.message_id, current_user)
    user_id = current_user.id
    
    # Check for existing vote
    stmt = select(ConversationVote).where(
        ConversationVote.conversation_id == payload.conversation_id,
        ConversationVote.message_id == payload.message_id,
        ConversationVote.user_id == user_id,
    )
    result = session.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        # Update existing vote
        old_vote = existing.vote
        existing.vote = payload.vote
        existing.reason = payload.reason
        existing.confidence = payload.confidence
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        
        # Log analytics event
        _log_vote_event(
            "vote_updated",
            existing,
            {"old_vote": old_vote, "new_vote": payload.vote}
        )
        
        return VoteResponse(vote_id=existing.id, action="updated")
    # Create under a savepoint. If a concurrent request wins the unique-key
    # race, update that row instead of returning a 500 or creating duplicates.
    vote = ConversationVote(
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        user_id=user_id,
        vote=payload.vote,
        reason=payload.reason,
        confidence=payload.confidence,
    )
    action = "created"
    try:
        with session.begin_nested():
            session.add(vote)
            session.flush()
    except IntegrityError:
        vote = session.exec(stmt).first()
        if vote is None:
            raise
        vote.vote = payload.vote
        vote.reason = payload.reason
        vote.confidence = payload.confidence
        vote.updated_at = datetime.now(timezone.utc)
        session.add(vote)
        action = "updated"

    session.commit()
    session.refresh(vote)

    _log_vote_event("vote_cast" if action == "created" else "vote_updated", vote)
    if payload.reason:
        _log_vote_event("vote_reason_saved", vote)

    return VoteResponse(vote_id=vote.id, action=action)


@router.get("/summary", response_model=VoteSummary)
def get_vote_summary(
    conversation_id: str = Query(..., description="Conversation ID to summarize"),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Get aggregated vote summary for a conversation.
    
    Returns total_up, total_down, and net_score.
    """
    require_conversation_v2()
    require_debate_access(session.get(Debate, conversation_id), current_user, session)
    
    # Count up votes
    up_stmt = select(func.count()).where(
        ConversationVote.conversation_id == conversation_id,
        ConversationVote.vote == 1,
    )
    total_up = session.scalar(up_stmt) or 0
    
    # Count down votes
    down_stmt = select(func.count()).where(
        ConversationVote.conversation_id == conversation_id,
        ConversationVote.vote == -1,
    )
    total_down = session.scalar(down_stmt) or 0
    
    return VoteSummary(
        conversation_id=conversation_id,
        total_up=total_up,
        total_down=total_down,
        net_score=total_up - total_down,
        total_votes=total_up + total_down,
    )


# -----------------------------------------------------------------------------
# Analytics Helpers (Patchset 78)
# -----------------------------------------------------------------------------

def _log_vote_event(
    event_name: str,
    vote: ConversationVote,
    extra: dict = None,
) -> None:
    """
    Emit structured analytics event for voting.
    
    No PII - only IDs and vote values.
    """
    payload = {
        "event": event_name,
        "conversation_id": vote.conversation_id,
        "message_id": vote.message_id,
        "vote": vote.vote,
        "has_reason": bool(vote.reason),
        "has_confidence": vote.confidence is not None,
    }
    if extra:
        payload.update(extra)
    
    # Structured JSON log
    logger.info(f"analytics:{event_name}", extra={"analytics_payload": payload})
