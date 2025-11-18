import asyncio
import os
import uuid
from pathlib import Path
from time import time
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import func
from sqlmodel import Session, select

from metrics import increment_metric
from models import Debate, RatingPersona, Score, Team, TeamMember, User
from schemas import DebateConfig

CHANNELS: dict[str, asyncio.Queue] = {}
CHANNEL_META: dict[str, float] = {}
CHANNEL_TTL_SECS = int(os.getenv("CHANNEL_TTL_SECS", "7200"))
CHANNEL_SWEEP_INTERVAL = int(os.getenv("CHANNEL_SWEEP_INTERVAL", "60"))
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "1").lower() not in {"0", "false", "no"}

MAX_CALLS = int(os.getenv("RL_MAX_CALLS", "5"))
WINDOW = int(os.getenv("RL_WINDOW", "60"))
AUTH_MAX_CALLS = int(os.getenv("AUTH_RL_MAX_CALLS", "10"))
AUTH_WINDOW = int(os.getenv("AUTH_RL_WINDOW", "300"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _mark_channel(debate_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        CHANNEL_META[debate_id] = loop.time()
    except RuntimeError:
        CHANNEL_META[debate_id] = time()


def sweep_stale_channels(now: float | None = None) -> list[str]:
    if now is None:
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:
            now = time()
    stale = [key for key, created in CHANNEL_META.items() if now - created > CHANNEL_TTL_SECS]
    for debate_id in stale:
        CHANNELS.pop(debate_id, None)
        CHANNEL_META.pop(debate_id, None)
    return stale


async def channel_sweeper_loop() -> None:
    try:
        while True:
            sweep_stale_channels()
            await asyncio.sleep(CHANNEL_SWEEP_INTERVAL)
    except asyncio.CancelledError:
        raise


def cleanup_channel(debate_id: str) -> None:
    CHANNELS.pop(debate_id, None)
    CHANNEL_META.pop(debate_id, None)


def track_metric(name: str, value: int = 1) -> None:
    if ENABLE_METRICS:
        increment_metric(name, value)


def serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "role": user.role}


def members_from_config(config: DebateConfig) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    seen: set[str] = set()

    for agent in config.agents:
        agent_id = agent.name
        role = "critic" if "critic" in agent.name.lower() else "agent"
        members.append(
            {
                "id": agent_id,
                "name": agent.name,
                "role": role,
                "party": getattr(agent, "tools", None) and ", ".join(agent.tools or []) or None,
            }
        )
        seen.add(agent_id)

    for judge in config.judges:
        if judge.name in seen:
            continue
        members.append({"id": judge.name, "name": judge.name, "role": "judge"})
        seen.add(judge.name)

    return members


def serialize_team(team: Team, role: Optional[str] = None) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "created_at": team.created_at,
        "role": role,
    }


def serialize_rating_persona(row: RatingPersona) -> dict[str, Any]:
    badge = "NEW" if row.n_matches < 15 else None
    return {
        "persona": row.persona,
        "category": row.category,
        "elo": row.elo,
        "stdev": row.stdev,
        "n_matches": row.n_matches,
        "win_rate": row.win_rate,
        "ci": {"low": row.ci_low, "high": row.ci_high},
        "last_updated": row.last_updated.isoformat() if row.last_updated else None,
        "badge": badge,
    }


def user_team_role(session: Session, user_id: str, team_id: str) -> Optional[str]:
    row = session.exec(
        select(TeamMember.role).where(TeamMember.user_id == user_id, TeamMember.team_id == team_id)
    ).first()
    if isinstance(row, tuple):
        return row[0]
    return row


def user_is_team_member(session: Session, user: User, team_id: str) -> bool:
    if user.role == "admin":
        return True
    role = user_team_role(session, user.id, team_id)
    return role in {"owner", "editor", "viewer"}


def user_is_team_editor(session: Session, user: User, team_id: str) -> bool:
    if user.role == "admin":
        return True
    role = user_team_role(session, user.id, team_id)
    return role in {"owner", "editor"}


def user_team_ids(session: Session, user_id: str) -> list[str]:
    rows = session.exec(select(TeamMember.team_id).where(TeamMember.user_id == user_id)).all()
    return [row[0] if isinstance(row, tuple) else row for row in rows]


def can_access_debate(debate: Debate, user: Optional[User], session: Session) -> bool:
    if debate.user_id is None:
        return True
    if not user:
        return False
    if user.role == "admin":
        return True
    if debate.user_id == user.id:
        return True
    if debate.team_id:
        return user_is_team_member(session, user, debate.team_id)
    return False


def require_debate_access(debate: Optional[Debate], user: Optional[User], session: Session) -> Debate:
    from fastapi import HTTPException, status

    if not debate or not can_access_debate(debate, user, session):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debate not found")
    return debate


def avg_scores_for_debate(session: Session, debate_id: str) -> list[tuple[str, float]]:
    rows = (
        session.exec(select(Score.persona, func.avg(Score.score)).where(Score.debate_id == debate_id).group_by(Score.persona)).all()
    )
    result: list[tuple[str, float]] = []
    for row in rows:
        if isinstance(row, tuple):
            result.append((row[0], float(row[1])))
        else:
            result.append((row.persona, float(row.avg)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def champion_for_debate(session: Session, debate_id: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    scores = avg_scores_for_debate(session, debate_id)
    if not scores:
        return None, None, None
    champion_persona, champion_score = scores[0]
    runner_up = scores[1][1] if len(scores) > 1 else None
    return champion_persona, champion_score, runner_up


def excerpt(text: Optional[str], limit: int = 220) -> Optional[str]:
    if not text:
        return None
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def id_like(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4()}"
