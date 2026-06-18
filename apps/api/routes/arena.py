from typing import Any, Dict

from auth import get_current_user
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Request
from guards.llm_action_guard import require_llm_action_allowed
from models import Debate, DivergenceReport, User, UserInteraction, VoteRecord
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from worker.arena_tasks import _execute_divergence_computation

from routes.common import can_access_debate, require_debate_access

router = APIRouter(prefix="/arena", tags=["arena"])


class UserVotePayload(BaseModel):
    claim_id: str = Field(..., description="Stable identifier for the claim (SHA-256 of claim text)")
    claim_text: str = Field(..., description="The claim content the user voted on")


@router.get("/{debate_id}/divergence")
async def get_divergence_report(
    debate_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    request: Request = None,
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

        # Require auth + guard before triggering expensive LLM computation
        require_llm_action_allowed(
            user=current_user,
            action="divergence_recompute",
            session=session,
            debate_id=debate_id,
            ip_address=request.client.host if request.client else "0.0.0.0",
        )

        # Calculate on the fly if completed but report didn't process
        try:
            await _execute_divergence_computation(debate_id)
            report = session.exec(
                select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
            ).first()
        except Exception as exc:
            logger.warning("divergence_computation_failed debate_id=%s error=%s", debate_id, exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate claims divergence. Please try again later."
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
    """Cast a user agreement vote on a claim. Requires debate access."""
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)

    user_id = current_user.id

    # Validate claim_id exists in the divergence report
    report = session.exec(
        select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
    ).first()
    if not report or not report.ready:
        raise HTTPException(status_code=400, detail="Divergence report not available")

    all_claims = []
    for claim_group in [report.consensus_claims, report.contested_claims]:
        if claim_group and isinstance(claim_group, dict):
            for claim in claim_group.get("claims", []):
                if isinstance(claim, dict):
                    all_claims.append(claim.get("claim", ""))

    claim_texts = {c.strip().lower() for c in all_claims}
    if payload.claim_text.strip().lower() not in claim_texts:
        raise HTTPException(status_code=400, detail="Invalid claim_id — claim not found in divergence report")

    # Check for existing vote on this claim by this user
    existing_vote = session.exec(
        select(VoteRecord).where(
            VoteRecord.debate_id == debate_id,
            VoteRecord.user_id == user_id,
        )
    ).first()

    if existing_vote:
        existing_claim_text = (existing_vote.vote_json or {}).get("claim_text", "")
        if existing_claim_text.strip().lower() == payload.claim_text.strip().lower():
            raise HTTPException(status_code=400, detail="Already voted on this claim")

    # Record VoteRecord (server-validated data only, no client-trusted model_name/is_consensus)
    vote_record = VoteRecord(
        debate_id=debate_id,
        user_id=user_id,
        vote_json={
            "claim_id": payload.claim_id,
            "claim_text": payload.claim_text,
            "type": "arena_vote"
        }
    )
    session.add(vote_record)

    interaction = UserInteraction(
        user_id=user_id,
        debate_id=debate_id,
        interaction_type="arena_vote",
        details={
            "claim_id": payload.claim_id,
            "claim_text": payload.claim_text,
        }
    )
    session.add(interaction)
    session.commit()

    return {"success": True}
