"""
Centralized access control dependencies for debates and teams.

Provides reusable FastAPI dependencies for validating read/write permissions
on debates and team resources.

Patchset 36.0
"""

from typing import Optional

from auth import get_current_user, get_optional_user
from deps import get_session
from exceptions import NotFoundError, PermissionError
from fastapi import Depends
from models import Debate, Team, User
from routes.common import can_access_debate, user_is_team_member
from sqlmodel import Session


async def get_debate_with_read_access(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
) -> Debate:
    """
    Dependency to get a debate and validate read access.
    
    Args:
        debate_id: ID of the debate to access
        session: Database session
        current_user: Current authenticated user (optional)
        
    Returns:
        Debate object if access is granted
        
    Raises:
        NotFoundError: If debate doesn't exist
        PermissionError: If user lacks read access
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    
    # Check access permissions
    if not can_access_debate(debate, current_user, session):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")
    
    return debate


async def get_debate_with_write_access(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Debate:
    """
    Dependency to get a debate and validate write access.
    
    Args:
        debate_id: ID of the debate to modify
        session: Database session
        current_user: Current authenticated user (required)
        
    Returns:
        Debate object if write access is granted
        
    Raises:
        NotFoundError: If debate doesn't exist
        PermissionError: If user lacks write access
    """
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    
    # Write access requires ownership or admin role
    if not (current_user.role == "admin" or debate.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")
    
    return debate


async def get_team_with_membership(
    team_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Team:
    """
    Dependency to get a team and validate membership.
    
    Args:
        team_id: ID of the team to access
        session: Database session
        current_user: Current authenticated user (required)
        
    Returns:
        Team object if user is a member
        
    Raises:
        NotFoundError: If team doesn't exist
        PermissionError: If user is not a member
    """
    team = session.get(Team, team_id)
    if not team:
        raise NotFoundError(message="Team not found", code="team.not_found")
    
    # Check team membership
    if not (current_user.role == "admin" or user_is_team_member(session, current_user, team.id)):
        raise PermissionError(message="Not a team member", code="permission.denied")
    
    return team
