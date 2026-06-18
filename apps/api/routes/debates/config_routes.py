import logging
from typing import Optional

from auth import get_optional_user
from deps import get_session
from fastapi import APIRouter, Depends, Query, Response
from models import Debate, User
from schemas import DebateConfig, PanelConfig, default_debate_config
from sqlmodel import Session, select

from exceptions import NotFoundError
from routes.common import require_debate_access, serialize_rating_persona, track_metric
from routes.debates.dependencies import _members_from_config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config/default")
async def get_default_config():
    return default_debate_config()


@router.get("/leaderboard")
async def get_leaderboard(
    response: Response,
    category: Optional[str] = Query(default=None),
    min_matches: int = Query(0, ge=0, le=1000),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    from models import RatingPersona

    stmt = select(RatingPersona).order_by(RatingPersona.elo.desc())
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    if min_matches:
        stmt = stmt.where(RatingPersona.n_matches >= min_matches)
    stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()
    payload = {"items": [serialize_rating_persona(row) for row in rows]}
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/leaderboard/persona/{persona}")
async def get_leaderboard_persona(
    response: Response,
    persona: str,
    category: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    from models import RatingPersona

    stmt = select(RatingPersona).where(RatingPersona.persona == persona)
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    row = session.exec(stmt).first()
    if not row:
        raise NotFoundError(message="Persona not found", code="leaderboard.persona_not_found")
    payload = serialize_rating_persona(row)
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/debates/{debate_id}/members")
async def get_debate_members(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    panel = None
    if debate.panel_config:
        try:
            panel = PanelConfig.model_validate(debate.panel_config)
        except Exception:
            panel = None
    return {"members": _members_from_config(config, panel)}
