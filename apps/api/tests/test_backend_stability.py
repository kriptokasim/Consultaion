import pytest
from fastapi.testclient import TestClient
from config import settings

def test_config_production_safety_validation(monkeypatch):
    """Test that config defaults and validation enforce production safety (A1/A2)."""
    from config import AppSettings
    
    # Needs valid production secrets to reach the Patchset 107 checks
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "this-is-a-long-secure-jwt-secret-for-testing")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    
    # 1. Test USE_MOCK
    with pytest.raises(ValueError):
        monkeypatch.setenv("USE_MOCK", "1")
        monkeypatch.setenv("REQUIRE_REAL_LLM", "1")
        monkeypatch.setenv("ENABLE_SEC_HEADERS", "1")
        monkeypatch.setenv("ENABLE_CSRF", "1")
        AppSettings()

    # 2. Test REQUIRE_REAL_LLM
    with pytest.raises(ValueError):
        monkeypatch.setenv("USE_MOCK", "0")
        monkeypatch.setenv("REQUIRE_REAL_LLM", "0")
        monkeypatch.setenv("ENABLE_SEC_HEADERS", "1")
        monkeypatch.setenv("ENABLE_CSRF", "1")
        AppSettings()

    # 3. Test ENABLE_SEC_HEADERS
    with pytest.raises(ValueError):
        monkeypatch.setenv("USE_MOCK", "0")
        monkeypatch.setenv("REQUIRE_REAL_LLM", "1")
        monkeypatch.setenv("ENABLE_SEC_HEADERS", "0")
        monkeypatch.setenv("ENABLE_CSRF", "1")
        AppSettings()

def test_config_sse_backend_validation(monkeypatch):
    """Test SSE backend validation for multi-worker environments (C1)."""
    from config import AppSettings
    
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "this-is-a-long-secure-jwt-secret-for-testing")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("REQUIRE_REAL_LLM", "1")
    monkeypatch.setenv("ENABLE_SEC_HEADERS", "1")
    monkeypatch.setenv("ENABLE_CSRF", "1")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    monkeypatch.setenv("SSE_BACKEND", "memory")
    
    with pytest.raises(ValueError):
        AppSettings()

def test_exception_envelope(client: TestClient):
    """Test the normalized error envelope matches the expected schema (B1/B2/B3)."""
    response = client.get("/nonexistent_endpoint_for_test")
    # Should catch 404 and wrap it
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"
    assert "message" in data["error"]
    assert "retryable" in data["error"]

def test_debate_list_pagination(client: TestClient, db_session):
    """Test /debates pagination limits (D1)."""
    # Assuming the app allows default auth bypass or tests setup a user
    # 200 should exceed max limit of 100
    from models import User
    test_user = User(
        id="test_admin", 
        email="admin@example.com", 
        role="admin", 
        password_hash="mock",
        name="Admin"
    )
    db_session.add(test_user)
    db_session.commit()
    
    from auth import create_access_token
    token = create_access_token(user_id=test_user.id, email=test_user.email, role=test_user.role)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(
        "/debates?limit=200", 
        headers=headers
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"
    
    # 50 is allowed
    response = client.get(
        "/debates?limit=50", 
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert data["limit"] == 50
    assert "offset" in data
    assert "has_more" in data
