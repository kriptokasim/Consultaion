from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from auth import get_current_user, get_optional_user
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException
from models import Debate, Score, User, UserInteraction, UserPrediction
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from routes.common import can_access_debate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voting", tags=["voting"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class PredictionSubmit(BaseModel):
    predicted_winner: str = Field(..., description="The persona/model name predicted to win")
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Self-reported confidence score between 0.0 and 1.0")
    is_locked: Optional[bool] = Field(default=False, description="Whether to lock this prediction from further modifications")


def wilson_score_interval(pos: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate the Wilson score interval lower and upper bounds for a proportion."""
    if total == 0:
        return 0.0, 0.0
    z = 1.96  # 95% confidence level
    phat = pos / total
    denominator = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denominator
    spread = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total) / denominator
    return max(0.0, center - spread), min(1.0, center + spread)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/{debate_id}/predict")
async def cast_prediction(
    debate_id: str,
    payload: PredictionSubmit,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Submit or update a debate outcome prediction.
    Once locked, the prediction cannot be modified.
    Predictions are disabled once the debate finishes or fails.
    """
    debate = session.get(Debate, debate_id)
    if not debate or not can_access_debate(debate, current_user, session):
        raise HTTPException(status_code=404, detail="Debate not found.")

    if debate.status in ("completed", "completed_budget", "failed"):
        raise HTTPException(status_code=400, detail="Cannot predict outcomes of completed or failed debates.")

    stmt = select(UserPrediction).where(
        UserPrediction.debate_id == debate_id,
        UserPrediction.user_id == current_user.id
    )
    existing = session.exec(stmt).first()

    if existing and existing.is_locked:
        raise HTTPException(status_code=400, detail="Prediction is locked and cannot be updated.")

    if existing:
        existing.predicted_winner = payload.predicted_winner
        existing.confidence_score = payload.confidence_score
        if payload.is_locked:
            existing.is_locked = True
        session.add(existing)
    else:
        existing = UserPrediction(
            debate_id=debate_id,
            user_id=current_user.id,
            predicted_winner=payload.predicted_winner,
            confidence_score=payload.confidence_score,
            is_locked=payload.is_locked or False,
        )
        session.add(existing)

    session.commit()
    session.refresh(existing)

    # Log user interaction
    interaction = UserInteraction(
        user_id=current_user.id,
        debate_id=debate_id,
        interaction_type="voting_prediction",
        details={
            "prediction_id": existing.id,
            "predicted_winner": existing.predicted_winner,
            "confidence_score": existing.confidence_score,
            "is_locked": existing.is_locked
        }
    )
    session.add(interaction)
    session.commit()

    return {
        "success": True,
        "prediction": {
            "id": existing.id,
            "predicted_winner": existing.predicted_winner,
            "confidence_score": existing.confidence_score,
            "is_locked": existing.is_locked,
            "created_at": existing.created_at.isoformat()
        }
    }


@router.get("/{debate_id}/reveal")
async def reveal_prediction_and_reasons(
    debate_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    session: Session = Depends(get_session)
):
    """
    Get prediction outcomes, community aggregates, and judges' vote highlights/drawbacks.
    Resolves predictions on-the-fly if the debate is completed.
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found.")

    # Enforce access control for private debates
    if not can_access_debate(debate, current_user, session):
        raise HTTPException(status_code=404, detail="Debate not found.")

    # 1. Fetch current user's prediction
    user_id = current_user.id if current_user else None
    prediction = None
    if user_id:
        stmt = select(UserPrediction).where(
            UserPrediction.debate_id == debate_id,
            UserPrediction.user_id == user_id
        )
        prediction = session.exec(stmt).first()

    # 2. Resolve prediction on the fly if completed
    is_completed = debate.status in ("completed", "completed_budget")
    if is_completed:
        # Resolve user prediction if not resolved yet
        if prediction and not prediction.resolved_at:
            scores_stmt = select(Score).where(Score.debate_id == debate_id)
            scores = session.exec(scores_stmt).all()
            if scores:
                from collections import defaultdict
                persona_scores = defaultdict(list)
                for s in scores:
                    persona_scores[s.persona].append(s.score)
                avg_scores = {p: sum(val)/len(val) for p, val in persona_scores.items()}
                if avg_scores:
                    winner = max(avg_scores, key=avg_scores.get)
                    prediction.is_correct = (prediction.predicted_winner == winner)
                    prediction.resolved_at = datetime.now(timezone.utc)
                    session.add(prediction)
                    session.commit()
                    session.refresh(prediction)

        # Trigger vote reasons LLM extraction if not pre-computed
        if not debate.final_meta or "vote_reasons" not in debate.final_meta:
            from worker.voting_tasks import _execute_vote_reasons_extraction
            try:
                # Execute synchronously on-the-fly
                await _execute_vote_reasons_extraction(debate_id)
                session.refresh(debate)
            except Exception as exc:
                logger.warning("Failed on-the-fly vote reasons extraction for %s: %s", debate_id, exc)

    # 3. Get community aggregates
    total_predictions = session.scalar(
        select(func.count(UserPrediction.id)).where(UserPrediction.debate_id == debate_id)
    ) or 0

    stmt_agg = (
        select(UserPrediction.predicted_winner, func.count(UserPrediction.id), func.avg(UserPrediction.confidence_score))
        .where(UserPrediction.debate_id == debate_id)
        .group_by(UserPrediction.predicted_winner)
    )
    results = session.exec(stmt_agg).all()

    aggregates = []
    for candidate, count, avg_conf in results:
        lower, upper = wilson_score_interval(count, total_predictions)
        aggregates.append({
            "candidate": candidate,
            "count": count,
            "percentage": float(round((count / total_predictions) * 100, 1)) if total_predictions > 0 else 0.0,
            "mean_confidence": float(round(avg_conf or 0.0, 2)),
            "wilson_lower": float(round(lower, 3)),
            "wilson_upper": float(round(upper, 3))
        })

    return {
        "debate_id": debate_id,
        "prediction": {
            "predicted_winner": prediction.predicted_winner,
            "confidence_score": prediction.confidence_score,
            "is_locked": prediction.is_locked,
            "is_correct": prediction.is_correct,
            "resolved_at": prediction.resolved_at.isoformat() if prediction.resolved_at else None
        } if prediction else None,
        "aggregates": aggregates,
        "vote_reasons": debate.final_meta.get("vote_reasons") if debate.final_meta else None
    }
