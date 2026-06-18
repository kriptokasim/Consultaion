import hashlib
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arena", tags=["arena"])


def _normalize_claim_text(text: str) -> str:
    """Canonical normalization for claim identity hashing."""
    return " ".join(text.strip().lower().split())


def _compute_claim_id(claim_text: str) -> str:
    """Server-side SHA-256 of normalized claim text."""
    normalized = _normalize_claim_text(claim_text)
    return hashlib.sha256(normalized.encode()).hexdigest()


class UserVotePayload(BaseModel):
    claim_id: str = Field(..., description="Server-computed SHA-256 of normalized claim text")
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

        require_llm_action_allowed(
            user=current_user,
            action="divergence_recompute",
            session=session,
            debate_id=debate_id,
            ip_address=request.client.host if request.client else "0.0.0.0",
        )

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

    # Report existence means it's ready (no `ready` column on DivergenceReport)
    report = session.exec(
        select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
    ).first()
    if not report:
        raise HTTPException(status_code=400, detail="Divergence report not available")

    # Build claim text set and validate claim_id server-side
    all_claims = []
    for claim_group in [report.consensus_claims, report.contested_claims]:
        if claim_group and isinstance(claim_group, dict):
            for claim in claim_group.get("claims", []):
                if isinstance(claim, dict):
                    text = claim.get("claim", "")
                    if text:
                        all_claims.append(text)

    # Validate claim_id matches server-computed SHA-256
    claim_text_lower = payload.claim_text.strip().lower()
    found = False
    for claim_text in all_claims:
        if claim_text.strip().lower() == claim_text_lower:
            found = True
            # Verify claim_id matches server-side computation
            expected_id = _compute_claim_id(claim_text)
            if payload.claim_id != expected_id:
                raise HTTPException(status_code=400, detail="Invalid claim_id — hash mismatch")
            break

    if not found:
        raise HTTPException(status_code=400, detail="Invalid claim — not found in divergence report")

    # Check for existing vote on this claim by this user
    existing_vote = session.exec(
        select(VoteRecord).where(
            VoteRecord.debate_id == debate_id,
            VoteRecord.user_id == user_id,
        )
    ).first()

    if existing_vote:
        existing_claim_text = (existing_vote.vote_json or {}).get("claim_text", "")
        if existing_claim_text.strip().lower() == claim_text_lower:
            raise HTTPException(status_code=400, detail="Already voted on this claim")

    # Record VoteRecord
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
