from uuid import uuid4
from models import User, RedTeamSession
from sqlmodel import Session, select
import pytest
from routes.redteam import run_analysis_task

def test_start_red_team_session_endpoint(authenticated_client, db_session: Session):
    payload = {
        "proposal_text": "We will host our database without a password in public access.",
        "lenses": ["security", "compliance"]
    }
    response = authenticated_client.post('/redteam', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["proposal_text"] == "We will host our database without a password in public access."
    assert data["status"] == "processing"
    assert data["lenses"] == ["security", "compliance"]

    # Verify session is persisted
    db_session.expire_all()
    session_id = data["id"]
    rt = db_session.get(RedTeamSession, session_id)
    assert rt is not None
    assert rt.proposal_text == "We will host our database without a password in public access."


def test_get_red_team_session_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    rt = RedTeamSession(
        id=str(uuid4()),
        user_id=user.id,
        proposal_text="Our pricing plans will dynamically charge user credit cards without invoice notifications.",
        lenses={"list": ["financial", "compliance"]},
        critique_matrix={
            "issues": [
                {
                    "lens": "financial",
                    "title": "Violates payment processor agreements",
                    "severity": "high",
                    "description": "Charging credit cards without invoices violates compliance standards.",
                    "remediation": "Incorporate billing notifications before charge execution."
                }
            ]
        }
    )
    db_session.add(rt)
    db_session.commit()

    response = authenticated_client.get(f'/redteam/{rt.id}')
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rt.id
    assert data["status"] == "completed"
    assert len(data["issues"]) == 1
    assert data["issues"][0]["lens"] == "financial"
    assert data["issues"][0]["severity"] == "high"


@pytest.mark.anyio
async def test_red_team_analysis_background_task(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    rt = RedTeamSession(
        id=str(uuid4()),
        user_id=user.id,
        proposal_text="Use unsecured memory caches globally.",
        lenses={"list": ["security"]},
        critique_matrix=None
    )
    db_session.add(rt)
    db_session.commit()

    # Run the background analysis task directly
    await run_analysis_task(rt.id, rt.proposal_text, ["security"])

    db_session.expire_all()
    updated_rt = db_session.get(RedTeamSession, rt.id)
    assert updated_rt is not None
    assert updated_rt.critique_matrix is not None
    assert "issues" in updated_rt.critique_matrix
    issues = updated_rt.critique_matrix["issues"]
    assert len(issues) > 0
    assert issues[0]["lens"] == "security"
