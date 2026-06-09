from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from auth import get_current_user, get_optional_user
from deps import get_session
from models import User, Debate, DivergenceReport, VoteRecord, UserInteraction
from worker.arena_tasks import _execute_divergence_computation
from routes.common import can_access_debate

router = APIRouter(prefix="/arena", tags=["arena"])


class UserVotePayload(BaseModel):
    claim_text: str = Field(..., description="The claim content the user voted on")
    model_name: str = Field(..., description="The name of the model that produced the claim")
    is_consensus: bool = Field(..., description="Whether the claim was categorized as consensus or contested")


@router.get("/{debate_id}/divergence")
async def get_divergence_report(
    debate_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Retrieve claims divergence report. Computes it on the fly if missing on a completed run."""
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Enforce access control: private debates are not readable by unauthorized users
    if not can_access_debate(debate, current_user, session):
        raise HTTPException(status_code=404, detail="Debate not found")

    report = session.exec(
        select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
    ).first()

    if not report:
        if debate.status != "completed":
            return {
                "debate_id": debate_id,
                "status": debate.status,
                "divergence_score": 0.0,
                "consensus_claims": {"claims": []},
                "contested_claims": {"claims": []},
                "ready": False
            }
        
        # Calculate on the fly if completed but report didn't process
        try:
            await _execute_divergence_computation(debate_id)
            report = session.exec(
                select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
            ).first()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to calculate claims divergence: {str(exc)}"
            )

    if not report:
        raise HTTPException(status_code=404, detail="Divergence report not found")

    return {
        "id": report.id,
        "debate_id": report.debate_id,
        "divergence_score": report.divergence_score,
        "consensus_claims": report.consensus_claims or {"claims": []},
        "contested_claims": report.contested_claims or {"claims": []},
        "created_at": report.created_at.isoformat(),
        "ready": True
    }


@router.post("/{debate_id}/user-vote")
async def cast_arena_vote(
    debate_id: str,
    payload: UserVotePayload,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Cast a user agreement vote on a consensus or contested claim."""
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    user_id = current_user.id

    # Check for existing vote record in this debate by this user
    # Note: We query user interactions of type 'arena_vote' for this debate
    existing_interaction = session.exec(
        select(UserInteraction).where(
            UserInteraction.debate_id == debate_id,
            UserInteraction.user_id == user_id,
            UserInteraction.interaction_type == "arena_vote"
        )
    ).first()

    if existing_interaction:
        raise HTTPException(status_code=400, detail="User has already voted on this debate's claims")

    # Record VoteRecord
    vote_record = VoteRecord(
        debate_id=debate_id,
        user_id=user_id,
        vote_json={
            "claim_text": payload.claim_text,
            "model_name": payload.model_name,
            "is_consensus": payload.is_consensus,
            "type": "arena_vote"
        }
    )
    session.add(vote_record)

    # Record UserInteraction for participation history
    interaction = UserInteraction(
        user_id=user_id,
        debate_id=debate_id,
        interaction_type="arena_vote",
        details={
            "claim_text": payload.claim_text,
            "model_name": payload.model_name,
            "is_consensus": payload.is_consensus
        }
    )
    session.add(interaction)
    session.commit()

    return {"success": True}
