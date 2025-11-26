"""Admin endpoints for routing observability and debugging."""
from typing import Optional

from auth import get_current_admin
from deps import get_session
from fastapi import APIRouter, Depends, Query
from models import User
from parliament.router_v2 import RouteContext, choose_model
from sqlmodel import Session

router = APIRouter(prefix="/admin/routing", tags=["admin", "routing"])


@router.get("/preview")
def routing_preview(
    requested_model: Optional[str] = Query(None, description="Explicit model ID to test"),
    routing_policy: Optional[str] = Query(None, description="Routing policy: 'router-smart' or 'router-deep'"),
    user_id: Optional[str] = Query(None, description="User ID for context"),
    team_id: Optional[str] = Query(None, description="Team ID for context"),
    debate_type: Optional[str] = Query(None, description="Debate type for context"),
    estimated_tokens: Optional[int] = Query(None, description="Estimated token count"),
    priority: str = Query("normal", description="Priority: 'normal' or 'high'"),
    safety_level: str = Query("normal", description="Safety level: 'strict', 'normal', or 'relaxed'"),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Preview routing decisions without creating a debate.
    
    Returns the selected model and a ranked list of all candidates with their scores.
    Useful for debugging and understanding how the routing engine makes decisions.
    """
    ctx = RouteContext(
        user_id=user_id,
        team_id=team_id,
        requested_model=requested_model,
        routing_policy=routing_policy,
        debate_type=debate_type,
        estimated_tokens=estimated_tokens,
        priority=priority,  # type: ignore
        safety_level=safety_level,  # type: ignore
    )
    
    selected_model, candidates = choose_model(ctx)
    
    return {
        "selected_model": selected_model,
        "policy_used": routing_policy or "router-smart",
        "explicit_override": requested_model is not None,
        "candidates": [
            {
                "model": c.model,
                "total_score": round(c.total_score, 3),
                "cost_score": round(c.cost_score, 3),
                "latency_score": round(c.latency_score, 3),
                "quality_score": round(c.quality_score, 3),
                "safety_score": round(c.safety_score, 3),
                "is_healthy": c.is_healthy,
                "details": c.details,
            }
            for c in candidates
        ],
        "context": {
            "user_id": user_id,
            "team_id": team_id,
            "requested_model": requested_model,
            "routing_policy": routing_policy,
            "debate_type": debate_type,
            "estimated_tokens": estimated_tokens,
            "priority": priority,
            "safety_level": safety_level,
        },
    }
