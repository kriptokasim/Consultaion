from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from models import User, UserInteraction
from deps import get_session
from auth import get_current_user

router = APIRouter(tags=["participation"])

@router.get("/users/me/participation")
async def get_user_participation(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Retrieve participation statistics and recent interactions for the authenticated user."""
    user_id = current_user.id

    # Count interactions by type
    stmt = (
        select(UserInteraction.interaction_type, func.count(UserInteraction.id))
        .where(UserInteraction.user_id == user_id)
        .group_by(UserInteraction.interaction_type)
    )
    counts_raw = session.exec(stmt).all()
    counts = {interaction_type: count for interaction_type, count in counts_raw}

    # Fetch 10 most recent interactions
    recent_stmt = (
        select(UserInteraction)
        .where(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.created_at.desc())
        .limit(10)
    )
    recent = session.exec(recent_stmt).all()

    # Format response payload
    return {
        "stats": {
            "total_interactions": sum(counts.values()),
            "arena_votes": counts.get("arena_vote", 0),
            "debate_steers": counts.get("debate_moderation", 0),
            "voting_predictions": counts.get("voting_prediction", 0),
            "redteam_critiques": counts.get("redteam_critique", 0),
            "oracle_branches": counts.get("oracle_branch", 0),
            "challenge_pushbacks": counts.get("challenge_pushback", 0),
        },
        "recent_activity": [
            {
                "id": item.id,
                "debate_id": item.debate_id,
                "type": item.interaction_type,
                "details": item.details,
                "created_at": item.created_at.isoformat(),
            }
            for item in recent
        ],
    }
