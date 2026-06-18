import logging
from typing import Optional

from auth import get_current_user
from deps import get_session
from exceptions import NotFoundError
from fastapi import APIRouter, Depends
from models import Debate, User
from pydantic import BaseModel
from sqlmodel import Session, select

from routes.common import (
    require_debate_access,
    require_debate_mutation_access,
    user_is_team_member,
)
from audit import record_audit

logger = logging.getLogger(__name__)

router = APIRouter()


class DebateShare(BaseModel):
    is_public: bool


class DebateModerateRequest(BaseModel):
    round_index: int
    moderation_steering: str


@router.post("/debates/{debate_id}/share")
async def share_debate(
    debate_id: str,
    body: DebateShare,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = require_debate_mutation_access(session.get(Debate, debate_id), current_user, session)

    if not debate.config:
        debate.config = {}
    
    config = dict(debate.config)
    config["is_public"] = body.is_public
    debate.config = config

    session.add(debate)
    session.commit()
    
    # Audit log
    record_audit(
        "debate_shared",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate.id,
        meta={"is_public": body.is_public},
        session=session,
    )
    
    return {"id": debate.id, "is_public": body.is_public}


@router.post("/debates/{debate_id}/moderate")
async def moderate_debate(
    debate_id: str,
    body: DebateModerateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from models import DebateTurn
    debate = require_debate_mutation_access(session.get(Debate, debate_id), current_user, session)

    stmt = select(DebateTurn).where(
        DebateTurn.debate_id == debate_id,
        DebateTurn.round_index == body.round_index,
        DebateTurn.agent_id == "moderator"
    )
    turn = session.exec(stmt).first()
    if turn:
        turn.moderation_steering = body.moderation_steering
        session.add(turn)
    else:
        turn = DebateTurn(
            debate_id=debate_id,
            round_index=body.round_index,
            agent_id="moderator",
            moderation_steering=body.moderation_steering
        )
        session.add(turn)
    session.commit()
    session.refresh(turn)

    return {
        "debate_id": debate_id,
        "round_index": body.round_index,
        "moderation_steering": body.moderation_steering
    }


@router.get("/debates/{debate_id}/argument-tree")
async def get_argument_tree(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from models import DebateTurn
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    
    stmt = select(DebateTurn).where(DebateTurn.debate_id == debate_id).order_by(DebateTurn.round_index.asc())
    turns = session.exec(stmt).all()

    raw_to_agent = {}
    for t in turns:
        if t.agent_id == "moderator":
            continue
        if t.claims_nodes:
            for node in t.claims_nodes:
                raw_id = node.get("id")
                if raw_id:
                    raw_to_agent[raw_id] = t.agent_id

    nodes = []
    for t in turns:
        # Skip moderator rows for tree nodes, but we could list them if needed.
        if t.agent_id == "moderator":
            continue
        if t.claims_nodes:
            for node in t.claims_nodes:
                target_raw = node.get("rebuts_target")
                target_agent = raw_to_agent.get(target_raw) if target_raw else None
                rebuts_target = f"{target_agent}_{target_raw}" if target_agent else None
                
                nodes.append({
                    "id": f"{t.agent_id}_{node.get('id')}",
                    "raw_id": node.get("id"),
                    "agent_id": t.agent_id,
                    "round_index": t.round_index,
                    "type": node.get("type"),
                    "claim": node.get("claim"),
                    "rebuts_target": rebuts_target,
                    "position_drift": t.position_drift
                })
    return {"nodes": nodes}
