import hashlib
import logging
from typing import Any, Dict

from auth import get_current_user
from database import SessionLocal
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Request
from guards.llm_action_guard import require_llm_action_allowed
from models import Debate, DivergenceReport, User, UserInteraction, VoteRecord
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from worker.arena_tasks import _execute_divergence_computation
from utils.async_bridge import run_blocking

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


def _load_debate_for_divergence(debate_id: str, current_user: User, session: Session) -> Debate:
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if not can_access_debate(debate, current_user, session):
        raise HTTPException(status_code=404, detail="Debate not found")

    return debate


def _load_divergence_report(debate_id: str, session: Session) -> DivergenceReport | None:
    return session.exec(
        select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
    ).first()


def _pending_divergence_payload(debate_id: str, debate_status: str) -> Dict[str, Any]:
    return {
        "debate_id": debate_id,
        "status": debate_status,
        "divergence_score": 0.0,
        "consensus_claims": {"claims": []},
        "contested_claims": {"claims": []},
        "ready": False
    }


def _divergence_payload(report: DivergenceReport) -> Dict[str, Any]:
    return {
        "id": report.id,
        "debate_id": report.debate_id,
        "divergence_score": report.divergence_score,
        "consensus_claims": report.consensus_claims or {"claims": []},
        "contested_claims": report.contested_claims or {"claims": []},
        "created_at": report.created_at.isoformat(),
        "ready": True
    }


@router.get("/{debate_id}/divergence")
async def get_divergence_report(
    debate_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Retrieve divergence without blocking the FastAPI event loop."""
    user_id = current_user.id
    def _read() -> Dict[str, Any]:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Debate not found")
            debate = _load_debate_for_divergence(debate_id, user, db)
            report = _load_divergence_report(debate_id, db)
            return _divergence_payload(report) if report else _pending_divergence_payload(debate_id, debate.status)
    return await run_blocking(_read)


@router.post("/{debate_id}/divergence")
async def compute_divergence_report(
    debate_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    request: Request = None,
) -> Dict[str, Any]:
    """Compute the claims divergence report on the fly for a completed run.

    Charges the caller for the computation; returns the cached report if one
    already exists.
    """
    debate = _load_debate_for_divergence(debate_id, current_user, session)

    report = _load_divergence_report(debate_id, session)

    if not report:
        if debate.status != "completed":
            return _pending_divergence_payload(debate_id, debate.status)

        await require_llm_action_allowed(
            user=current_user,
            action="divergence_recompute",
            session=session,
            debate_id=debate_id,
            ip_address=request.client.host if request.client else "unknown",
        )

        try:
            await _execute_divergence_computation(debate_id)
            report = _load_divergence_report(debate_id, session)
        except Exception as exc:
            logger.warning("divergence_computation_failed debate_id=%s error=%s", debate_id, exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate claims divergence. Please try again later."
            ) from exc

    if not report:
        raise HTTPException(status_code=404, detail="Divergence report not found")

    return _divergence_payload(report)


@router.post("/{debate_id}/user-vote")
async def cast_arena_vote(
    debate_id: str,
    payload: UserVotePayload,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Cast a vote using a thread-local DB session."""
    user_id = current_user.id
    def _write() -> Dict[str, Any]:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            require_debate_access(db.get(Debate, debate_id), user, db)
            report = db.exec(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)).first()
            if not report:
                raise HTTPException(status_code=400, detail="Divergence report not available")
            all_claims = []
            for claim_group in [report.consensus_claims, report.contested_claims]:
                if claim_group and isinstance(claim_group, dict):
                    for claim in claim_group.get("claims", []):
                        if isinstance(claim, dict) and claim.get("claim"):
                            all_claims.append(claim["claim"])
            claim_text_lower = payload.claim_text.strip().lower()
            found = next((t for t in all_claims if t.strip().lower() == claim_text_lower), None)
            if found is None:
                raise HTTPException(status_code=400, detail="Invalid claim — not found in divergence report")
            expected_id = _compute_claim_id(found)
            if payload.claim_id != expected_id:
                raise HTTPException(status_code=400, detail="Invalid claim_id — hash mismatch")
            existing_vote = db.exec(select(VoteRecord).where(VoteRecord.debate_id == debate_id, VoteRecord.user_id == user_id)).first()
            if existing_vote and (existing_vote.vote_json or {}).get("claim_text", "").strip().lower() == claim_text_lower:
                raise HTTPException(status_code=400, detail="Already voted on this claim")
            db.add(VoteRecord(debate_id=debate_id, user_id=user_id, vote_json={"claim_id": payload.claim_id, "claim_text": payload.claim_text, "type": "arena_vote"}))
            db.add(UserInteraction(user_id=user_id, debate_id=debate_id, interaction_type="arena_vote", details={"claim_id": payload.claim_id, "claim_text": payload.claim_text}))
            db.commit()
            return {"success": True}
    return await run_blocking(_write)
