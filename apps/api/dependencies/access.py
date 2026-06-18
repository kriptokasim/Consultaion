"""
Centralized access control dependencies for debates and teams.

Provides reusable FastAPI dependencies for validating read/write permissions
on debates and team resources.

Patchset 36.0 + FH125 Phase 2 (B-1)
"""

from typing import Optional

from auth import get_current_user, get_optional_user
from deps import get_session
from exceptions import NotFoundError, PermissionError
from fastapi import Depends
from log_config import update_log_context
from models import Debate, Team, User
from routes.common import can_access_debate, is_debate_owner, user_is_team_editor, user_is_team_member
from sqlmodel import Session


async def get_debate_with_read_access(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Debate:
    """
    Dependency to get a debate and validate read access.
    Returns 404 for unauthorized users (hides debate existence).
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")

    if not can_access_debate(debate, current_user, session):
        raise NotFoundError(message="Debate not found", code="debate.not_found")

    update_log_context(debate_id=getattr(debate, "id", None), team_id=getattr(debate, "team_id", None))
    return debate


async def get_debate_with_write_access(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Debate:
    """
    Dependency to get a debate and validate owner/admin write access.
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")

    if not is_debate_owner(debate, current_user):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    update_log_context(debate_id=getattr(debate, "id", None), team_id=getattr(debate, "team_id", None))
    return debate


async def get_debate_with_mutable_access(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Debate:
    """
    Dependency to get a debate and validate editor-level access.
    Allows: admin, debate owner, or team editor/owner.
    Returns 401 for unauthenticated, 403 for insufficient permissions.
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")

    if current_user.role == "admin" or getattr(current_user, "is_admin", False):
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate
    if debate.user_id == current_user.id:
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate
    if debate.team_id and user_is_team_editor(session, current_user, debate.team_id):
        update_log_context(debate_id=debate.id, team_id=debate.team_id)
        return debate

    raise PermissionError(message="Insufficient permissions", code="permission.denied")


async def get_team_with_membership(
    team_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Team:
    """
    Dependency to get a team and validate membership.
    """
    team = session.get(Team, team_id)
    if not team:
        raise NotFoundError(message="Team not found", code="team.not_found")

    if not (current_user.role == "admin" or user_is_team_member(session, current_user, team.id)):
        raise PermissionError(message="Not a team member", code="permission.denied")

    return team
