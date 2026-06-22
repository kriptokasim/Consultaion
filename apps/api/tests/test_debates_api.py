from uuid import uuid4

from models import Debate, Message, User
from sqlmodel import Session, select


def test_get_debate(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Test prompt for get", user_id=user.id, status="queued")
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
    for i in range(3):
        debate = Debate(id=str(uuid4()), prompt=f"List prompt {i}", user_id=user.id, status="queued")
        db_session.add(debate)
    db_session.commit()
    response = authenticated_client.get("/debates")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 3
    assert data["total"] >= 3

def test_update_debate(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    from models import Team, TeamMember
    team = Team(name="Test Team")
    db_session.add(team)
    db_session.commit()
    member = TeamMember(team_id=team.id, user_id=user.id, role="owner")
    db_session.add(member)
    db_session.commit()
    debate = Debate(id=str(uuid4()), prompt="Original prompt", user_id=user.id, status="queued")
    db_session.add(debate)
    db_session.commit()
    payload = {"team_id": team.id}
    response = authenticated_client.patch(f"/debates/{debate.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == team.id
    db_session.refresh(debate)
    assert debate.team_id == team.id

def test_start_debate_run(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Start me", user_id=user.id, status="queued")
    db_session.add(debate)
    db_session.commit()
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/debates/{debate.id}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"
        assert mock_dispatch.called
    db_session.refresh(debate)
    assert debate.status == "scheduled"

def test_get_debate_report(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Report me", user_id=user.id, status="completed")
    db_session.add(debate)
    db_session.commit()
    with patch("services.reporting.build_report") as mock_build:
        mock_build.return_value = {"debate": debate, "scores": [], "rounds": [], "messages_count": 0}
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
    with patch("services.reporting.build_report") as mock_build, patch("services.reporting.report_to_markdown") as mock_md:
        mock_build.return_value = {}
        mock_md.return_value = "# Markdown Report"
        response = authenticated_client.post(f"/debates/{debate.id}/export")
        assert response.status_code == 200
        assert response.text == "# Markdown Report"
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"

def test_admin_models_metadata(authenticated_client, db_session: Session):
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    authenticated_client.cookies.set(COOKIE_NAME, access_token)
    response = authenticated_client.get("/admin/models")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) > 0
    model = items[0]
    assert "recommended" in model
    assert "tiers" in model
    assert "cost" in model["tiers"]
    assert "latency" in model["tiers"]
    assert "quality" in model["tiers"]
    assert "safety" in model["tiers"]
    assert "tags" in model

def test_create_debate_rate_limit(authenticated_client, monkeypatch):
    monkeypatch.setenv("DEV_RL_DEBATE_CREATE_WINDOW", "60")
    monkeypatch.setenv("DEV_RL_DEBATE_CREATE_MAX_CALLS", "2")
    import config as config_module
    config_module.settings.reload()
    import ratelimit
    ratelimit.reset_rate_limiter_backend_for_tests()
    payload = {"prompt": "Rate limit test", "mode": "debate"}
    assert authenticated_client.post("/debates", json=payload).status_code == 200
    assert authenticated_client.post("/debates", json=payload).status_code == 200
    response = authenticated_client.post("/debates", json=payload)
    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == "rate_limit.exceeded"

def test_continue_debate_run(authenticated_client, db_session: Session):
    from unittest.mock import patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # 1. Test failure when status is not perspectives_ready
    debate = Debate(id=str(uuid4()), prompt="Continue me", user_id=user.id, status="queued")
    db_session.add(debate)
    db_session.commit()
    
    response = authenticated_client.post(f"/debates/{debate.id}/continue")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "debate.not_paused"
    
    # 2. Test success when status is perspectives_ready
    debate.status = "perspectives_ready"
    db_session.add(debate)
    db_session.commit()
    
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/debates/{debate.id}/continue")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"
        assert mock_dispatch.called
        
    db_session.refresh(debate)
    assert debate.status == "scheduled"


def test_retry_agent(authenticated_client, db_session: Session):
    from unittest.mock import AsyncMock, patch
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    panel_config = {
        "seats": [
            {
                "name": "Expert Agent",
                "model": "gpt-4o",
                "provider": "openai",
                "persona_tagline": "An AI expert helper"
            }
        ]
    }
    final_meta = {
        "models": [
            {
                "display_name": "Expert Agent",
                "model_id": "gpt-4o",
                "provider": "openai",
                "success": False
            }
        ],
        "total_count": 1,
        "successful_count": 0,
        "model_warnings": [
            {
                "display_name": "Expert Agent",
                "provider": "openai",
                "error": "Failed previously"
            }
        ]
    }
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Test agent retry",
        user_id=user.id,
        status="failed",
        panel_config=panel_config,
        final_meta=final_meta
    )
    db_session.add(debate)
    db_session.commit()
    
    with patch("agents.produce_candidate", new_callable=AsyncMock) as mock_produce:
        mock_produce.return_value = (
            {"text": "Retried agent response content", "tokens_used": 100},
            {"prompt_tokens": 10, "completion_tokens": 10}
        )
        
        response = authenticated_client.post(
            f"/debates/{debate.id}/retry-agent",
            json={"persona": "Expert Agent"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content"] == "Retried agent response content"
        
    db_session.refresh(debate)
    assert debate.final_meta["successful_count"] == 1
    assert len(debate.final_meta["model_warnings"]) == 0
    assert debate.final_meta["models"][0]["success"] is True

    msg = db_session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.round_index == 1,
            Message.persona == "Expert Agent"
        )
    ).first()
    assert msg is not None
    assert msg.content == "Retried agent response content"

def test_get_debate_with_continuation_row(authenticated_client, db_session: Session):
    import datetime
    from models import DebateContinuation
    
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(id=str(uuid4()), prompt="Test prompt with continuation", user_id=user.id, status="queued")
    db_session.add(debate)
    db_session.commit()
    
    # Create a continuation with the new columns to ensure serialization/ORM mapping handles it properly
    continuation = DebateContinuation(
        id=str(uuid4()),
        debate_id=debate.id,
        idempotency_key="test-idem-key-1",
        status="requested",
        cancelled_at=datetime.datetime.now(datetime.timezone.utc),
        paused_at=datetime.datetime.now(datetime.timezone.utc),
        failure_code="test_failure",
        failure_detail_safe="Test failure detail",
        credit_reservation_id="res_123"
    )
    db_session.add(continuation)
    db_session.commit()
    
    response = authenticated_client.get(f"/debates/{debate.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == debate.id
    assert data["prompt"] == "Test prompt with continuation"