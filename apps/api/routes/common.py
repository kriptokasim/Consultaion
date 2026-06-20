import logging
import uuid
from typing import Any, Optional

from config import settings
from log_config import update_log_context
from metrics import increment_metric
from models import Debate, RatingPersona, Score, Team, TeamMember, User
from schemas import DebateConfig, PanelConfig
from sqlalchemy import func
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

ENABLE_METRICS = settings.ENABLE_METRICS

MAX_CALLS = settings.RL_MAX_CALLS
WINDOW = settings.RL_WINDOW
AUTH_MAX_CALLS = settings.AUTH_RL_MAX_CALLS
AUTH_WINDOW = settings.AUTH_RL_WINDOW

def track_metric(name: str, value: int = 1) -> None:
    if ENABLE_METRICS:
        increment_metric(name, value)


def serialize_user(user: User) -> dict[str, Any]:
    from plan_config import resolve_plan_for_user
    from security.owner import is_owner
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "display_name": getattr(user, "display_name", None),
        "avatar_url": getattr(user, "avatar_url", None),
        "timezone": getattr(user, "timezone", None),
        "is_admin": bool(getattr(user, "is_admin", False) or user.role == "admin"),
        "is_active": getattr(user, "is_active", True),
        "email_summaries_enabled": getattr(user, "email_summaries_enabled", False),
        "plan": resolve_plan_for_user(user),
        "is_owner": is_owner(user),
    }


def members_from_config(config: DebateConfig, panel: PanelConfig | None = None) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    seen: set[str] = set()

    if panel and panel.seats:
        for seat in panel.seats:
            members.append(
                {
                    "id": seat.seat_id,
                    "name": seat.display_name,
                    "role": seat.role_profile,
                    "party": seat.provider_key,
                }
            )
        return members

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
    try:
        rows = session.exec(select(TeamMember.team_id).where(TeamMember.user_id == user_id)).all()
        return [row[0] if isinstance(row, tuple) else row for row in rows]
    except ProgrammingError as exc:
        msg = str(exc)
        if "UndefinedTable" in msg or 'relation "teammember" does not exist' in msg:
            logger.warning("TeamMember table missing; running in single-user/no-team mode.")
            return []
        raise


def can_access_debate(debate: Debate, user: Optional[User], session: Session) -> bool:
    if debate.user_id is None:
        return True
    
    # Allow public access if debate is explicitly shared
    if debate.config and debate.config.get("is_public") is True:
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
    update_log_context(debate_id=getattr(debate, "id", None), team_id=getattr(debate, "team_id", None))
    return debate


def is_debate_public(debate: Optional[Debate]) -> bool:
    """Check if a debate is explicitly shared as public."""
    if not debate or not debate.config:
        return False
    return debate.config.get("is_public") is True


def is_debate_owner(debate: Debate, user: Optional[User]) -> bool:
    """Check if user is the owner of the debate or an admin."""
    if not user:
        return False
    if user.role == "admin" or getattr(user, "is_admin", False):
        return True
    return debate.user_id == user.id


def require_debate_owner(debate: Optional[Debate], user: Optional[User], session: Session) -> Debate:
    """
    Require that the user is the debate owner or an admin.

    Used for mutation endpoints where only the owner should be able to act.
    Returns 401 for unauthenticated users, 403 for non-owners, 404 if debate
    doesn't exist.
    """
    from exceptions import NotFoundError, PermissionError as AppPermissionError
    from fastapi import HTTPException, status

    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    if not is_debate_owner(debate, user):
        raise AppPermissionError(message="Insufficient permissions", code="permission.denied")
    update_log_context(debate_id=getattr(debate, "id", None), team_id=getattr(debate, "team_id", None))
    return debate


def require_debate_mutation_access(debate: Optional[Debate], user: Optional[User], session: Session) -> Debate:
    """
    Require authenticated user with at least team-editor access for mutation.

    More permissive than require_debate_owner — allows team editors.
    Used for endpoints like start/restart where team members may act.
    """
    from exceptions import NotFoundError, PermissionError as AppPermissionError
    from fastapi import HTTPException, status

    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    if user.role == "admin" or getattr(user, "is_admin", False):
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate
    if debate.user_id == user.id:
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate
    if debate.team_id and user_is_team_editor(session, user, debate.team_id):
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate
    raise AppPermissionError(message="Insufficient permissions", code="permission.denied")


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


def require_schema_current(session: Session) -> None:
    """
    Guard mutation endpoints against running when schema is behind.

    Raises a 503 Service Unavailable with retryable=true when the DB schema
    has not reached the expected Alembic head revision.

    In ENV=test, the Alembic head check is bypassed because test databases
    are created with metadata.create_all() and have no alembic_version row.
    Table/column capability checks are still enforced.
    """
    from fastapi import HTTPException, status

    try:
        import os

        from services.schema_capabilities import get_registry, get_schema_capabilities

        is_test = os.environ.get("ENV", "").lower() == "test"

        caps = get_schema_capabilities(session, get_registry())

        # In test mode, only check table/column capabilities, not Alembic head
        if is_test:
            # Filter out the schema_behind_head marker for test environments
            non_alembic_missing = [
                c for c in caps.missing_capabilities
                if c != "schema_behind_head"
            ]
            if non_alembic_missing:
                logger.debug(
                    "schema_current_check_test_bypass: still missing capabilities=%s",
                    non_alembic_missing,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "schema_upgrade_required",
                        "retryable": True,
                        "message": "Database schema is missing required tables/columns. "
                                   "Mutations are blocked until the schema is upgraded.",
                    },
                )
            return

        # Production/staging: full check including Alembic head
        if not caps.is_at_alembic_head or caps.missing_capabilities:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "schema_upgrade_required",
                    "retryable": True,
                    "message": "Database schema is behind the application version. "
                               "Mutations are blocked until the schema is upgraded.",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("schema_current_check_failed error=%s", exc)


def excerpt(text: Optional[str], limit: int = 220) -> Optional[str]:
    if not text:
        return None
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def id_like(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4()}"
