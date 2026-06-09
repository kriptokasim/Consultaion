from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from auth import get_current_user
from deps import get_session
from models import User, RedTeamSession, UserInteraction
from orchestration.redteam import run_red_team_analysis
from exceptions import NotFoundError, PermissionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/redteam", tags=["redteam"])

class RedTeamCreate(BaseModel):
    proposal_text: str = Field(..., min_length=10, description="The proposal text to review")
    lenses: List[str] = Field(default_factory=lambda: ["security", "scaling", "compliance"], description="The risk lenses to evaluate")


async def run_analysis_task(session_id: str, proposal_text: str, lenses: List[str]):
    try:
        from database_async import async_session_scope
        from sqlmodel import select
        matrix = await run_red_team_analysis(proposal_text, lenses)
        async with async_session_scope() as db_session:
            stmt = select(RedTeamSession).where(RedTeamSession.id == session_id)
            res = await db_session.execute(stmt)
            rt_session = res.scalars().first()
            if rt_session:
                rt_session.critique_matrix = {"issues": matrix}
                db_session.add(rt_session)
                await db_session.commit()
    except Exception as exc:
        logger.error(f"Failed background red team task: {exc}")


@router.post("")
async def start_red_team_session(
    payload: RedTeamCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Starts an adversarial critique Red Team session for the given proposal text.
    Runs the risk evaluation asynchronously in the background.
    """
    rt_session = RedTeamSession(
        user_id=current_user.id,
        proposal_text=payload.proposal_text,
        lenses={"list": payload.lenses},
        critique_matrix=None
    )
    session.add(rt_session)
    session.commit()
    session.refresh(rt_session)

    # Log interaction for participation tracking
    interaction = UserInteraction(
        user_id=current_user.id,
        interaction_type="redteam_critique",
        details={
            "entity_id": rt_session.id,
            "label": "redteam_session",
            "summary": payload.proposal_text[:200],
            "status": "created"
        }
    )
    session.add(interaction)
    session.commit()

    # Queue the analysis task
    background_tasks.add_task(
        run_analysis_task,
        rt_session.id,
        payload.proposal_text,
        payload.lenses
    )

    return {
        "id": rt_session.id,
        "proposal_text": rt_session.proposal_text,
        "lenses": payload.lenses,
        "status": "processing",
        "created_at": rt_session.created_at
    }


@router.get("/{session_id}")
async def get_red_team_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieves a Red Team session, its current status, and any completed critiques.
    """
    rt_session = session.get(RedTeamSession, session_id)
    if not rt_session:
        raise NotFoundError(message="Red Team session not found", code="redteam.not_found")
    
    if not (current_user.role == "admin" or rt_session.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    issues = []
    status = "processing"
    if rt_session.critique_matrix and "issues" in rt_session.critique_matrix:
        issues = rt_session.critique_matrix["issues"]
        status = "completed"

    return {
        "id": rt_session.id,
        "proposal_text": rt_session.proposal_text,
        "lenses": rt_session.lenses.get("list", []) if rt_session.lenses else [],
        "status": status,
        "issues": issues,
        "created_at": rt_session.created_at
    }

# Alias for router inclusion
redteam_router = router
