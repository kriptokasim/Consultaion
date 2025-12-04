
from uuid import uuid4

from models import Debate, User
from sqlmodel import Session, select


def test_get_debate(authenticated_client, db_session: Session):
    # Get the user created by the fixture
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Test prompt for get",
        user_id=user.id,
        status="queued"
    )
    db_session.add(debate)
    db_session.commit()
    
    response = authenticated_client.get(f"/debates/{debate.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == debate.id
    assert data["prompt"] == "Test prompt for get"

def test_get_debate_not_found(authenticated_client):
    response = authenticated_client.get(f"/debates/{uuid4()}")
    assert response.status_code == 404

def test_list_debates(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create a few debates
    for i in range(3):
        debate = Debate(
            id=str(uuid4()),
            prompt=f"List prompt {i}",
            user_id=user.id,
            status="queued"
        )
        db_session.add(debate)
    db_session.commit()
    
    response = authenticated_client.get("/debates")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 3
    assert data["total"] >= 3

def test_update_debate(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create a team
    from models import Team, TeamMember
    team = Team(name="Test Team")
    db_session.add(team)
    db_session.commit()
    
    member = TeamMember(team_id=team.id, user_id=user.id, role="owner")
    db_session.add(member)
    db_session.commit()
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Original prompt",
        user_id=user.id,
        status="queued"
    )
    db_session.add(debate)
    db_session.commit()
    
    payload = {"team_id": team.id}
    response = authenticated_client.patch(f"/debates/{debate.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == team.id
    
    # Verify DB
    db_session.refresh(debate)
    assert debate.team_id == team.id

def test_start_debate_run(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Start me",
        user_id=user.id,
        status="queued"
    )
    db_session.add(debate)
    db_session.commit()
    
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/debates/{debate.id}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"
        assert mock_dispatch.called
    
    # Verify DB
    db_session.refresh(debate)
    assert debate.status == "scheduled"

def test_get_debate_report(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Report me", user_id=user.id, status="completed")
    db_session.add(debate)
    db_session.commit()
    
    with patch("services.reporting.build_report") as mock_build:
        mock_build.return_value = {
            "debate": debate,
            "scores": [],
            "rounds": [],
            "messages_count": 0
        }
        response = authenticated_client.get(f"/debates/{debate.id}/report")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == debate.id
        assert data["status"] == "completed"

def test_export_debate_report(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Export me", user_id=user.id, status="completed")
    db_session.add(debate)
    db_session.commit()
    
    with patch("services.reporting.build_report") as mock_build, \
         patch("services.reporting.report_to_markdown") as mock_md:
        mock_build.return_value = {}
        mock_md.return_value = "# Markdown Report"
        
        response = authenticated_client.post(f"/debates/{debate.id}/export")
        assert response.status_code == 200
        assert response.text == "# Markdown Report"
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"

def test_admin_models_metadata(authenticated_client, db_session: Session):
    # We need to be an admin to access this endpoint
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    # Create admin user
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    
    # Login as admin
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    
    response = authenticated_client.get("/admin/models")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) > 0
    
    # Check for new fields
    model = items[0]
    assert "recommended" in model
    assert "tiers" in model
    assert "cost" in model["tiers"]
    assert "latency" in model["tiers"]
    assert "quality" in model["tiers"]
    assert "safety" in model["tiers"]
    assert "tags" in model


