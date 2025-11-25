
from audit import record_audit
from auth import get_current_user
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException
from models import Team, TeamMember, User
from sqlmodel import Session, select

from routes.common import serialize_team, user_is_team_editor, user_is_team_member

router = APIRouter(tags=["teams"])


class TeamCreatePayload(Team := object):  # type: ignore
    ...


from pydantic import BaseModel  # noqa: E402


class TeamCreate(BaseModel):  # type: ignore[no-redef]
    name: str


class TeamMemberCreate(BaseModel):
    email: str
    role: str = "viewer"


def _get_team_or_404(session: Session, team_id: str) -> Team:
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    return team


@router.post("/teams")
async def create_team(
    body: TeamCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="team name required")
    team = Team(name=name)
    session.add(team)
    session.commit()
    session.refresh(team)
    session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="owner"))
    session.commit()
    record_audit(
        "team_created",
        user_id=current_user.id,
        target_type="team",
        target_id=team.id,
        meta={"name": team.name},
        session=session,
    )
    return serialize_team(team, "owner")


@router.get("/teams")
async def list_teams(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rows = session.exec(
        select(Team, TeamMember.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == current_user.id)
        .order_by(Team.created_at.desc())
    ).all()
    items = [serialize_team(team, role) for team, role in rows]
    return {"items": items}


@router.get("/teams/{team_id}/members")
async def list_team_members(
    team_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = _get_team_or_404(session, team_id)
    if not user_is_team_member(session, current_user, team.id):
        raise HTTPException(status_code=403, detail="not a team member")
    rows = session.exec(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.created_at.asc())
    ).all()
    return {
        "team": serialize_team(team),
        "members": [
            {
                "id": member.id,
                "user_id": user.id,
                "email": user.email,
                "role": member.role,
                "created_at": member.created_at,
            }
            for member, user in rows
        ],
    }


@router.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    body: TeamMemberCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = _get_team_or_404(session, team_id)
    if not user_is_team_editor(session, current_user, team.id):
        raise HTTPException(status_code=403, detail="only owners can manage members")
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    member = session.exec(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
    ).first()
    if member:
        member.role = body.role
        session.add(member)
    else:
        member = TeamMember(team_id=team.id, user_id=user.id, role=body.role)
        session.add(member)
    session.commit()
    record_audit(
        "team_member_added",
        user_id=current_user.id,
        target_type="team",
        target_id=team.id,
        meta={"member_id": member.user_id, "role": member.role},
        session=session,
    )
    return {
        "id": member.id,
        "team_id": member.team_id,
        "user_id": member.user_id,
        "role": member.role,
    }


teams_router = router
