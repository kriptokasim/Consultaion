import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import Session, select
from auth import COOKIE_NAME, create_access_token, hash_password
from models import User

def _setup_admin(db_session: Session, client):
    admin_email = "admin@example.com"
    admin = db_session.exec(select(User).where(User.email == admin_email)).first()
    if not admin:
        admin = User(email=admin_email, password_hash=hash_password("password"), role="admin")
        db_session.add(admin)
        db_session.commit()
    
    access_token = create_access_token(user_id=admin.id, email=admin.email, role="admin")
    client.cookies.set(COOKIE_NAME, access_token)
    return admin

def test_admin_providers_health(authenticated_client, db_session: Session):
    _setup_admin(db_session, authenticated_client)
    
    response = authenticated_client.get("/admin/providers/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "providers" in data
    assert "openai" in data["providers"]
    assert "status" in data["providers"]["openai"]

@pytest.mark.anyio
async def test_admin_test_provider_missing_key(authenticated_client, db_session: Session):
    _setup_admin(db_session, authenticated_client)
    
    with patch("config.settings.OPENAI_API_KEY", None):
        response = authenticated_client.post("/admin/providers/openai/test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "API key is not configured" in data["error"]

@pytest.mark.anyio
async def test_admin_test_provider_success(authenticated_client, db_session: Session):
    _setup_admin(db_session, authenticated_client)
    
    # Mock Litellm completion
    mock_choice = AsyncMock()
    mock_choice.message = {"content": "pong"}
    mock_response = AsyncMock()
    mock_response.choices = [mock_choice]
    
    with patch("config.settings.OPENAI_API_KEY", "mock-key"):
        with patch("litellm.acompletion", return_value=mock_response) as mock_acompletion:
            response = authenticated_client.post("/admin/providers/openai/test")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["response"] == "pong"
            assert data["model_tested"] == "openai/gpt-4o-mini"
            mock_acompletion.assert_called_once()
