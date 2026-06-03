from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
@patch("config.settings.OPENAI_API_KEY", "sk-test-openai")
@patch("config.settings.ANTHROPIC_API_KEY", "sk-test-anthropic")
@patch("config.settings.GEMINI_API_KEY", "sk-test-gemini")
@patch("config.settings.OPENROUTER_API_KEY", "sk-test-openrouter")
def test_api_status_success(mock_sse, mock_db, client):
    """Test /api/status when database and SSE are operational, and all SOTA provider keys are configured."""
    mock_db.return_value = (True, {"ping": True})
    mock_sse.return_value = (True, {"ok": True})
    
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["database"] == "operational"
    assert data["sse"] == "operational"
    assert data["providers"]["openai"]["configured"] is True
    assert data["providers"]["openai"]["status"] == "operational"
    assert data["providers"]["anthropic"]["configured"] is True
    assert data["providers"]["gemini"]["configured"] is True
    assert data["providers"]["openrouter"]["configured"] is True

@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
@patch("config.settings.OPENAI_API_KEY", None)
@patch("config.settings.ANTHROPIC_API_KEY", "sk-test-anthropic")
@patch("config.settings.GEMINI_API_KEY", None)
@patch("config.settings.OPENROUTER_API_KEY", None)
def test_api_status_degraded(mock_sse, mock_db, client):
    """Test /api/status when database and SSE are operational but some provider keys are missing."""
    mock_db.return_value = (True, {"ping": True})
    mock_sse.return_value = (True, {"ok": True})
    
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["providers"]["openai"]["configured"] is False
    assert data["providers"]["openai"]["status"] == "not_configured"
    assert data["providers"]["anthropic"]["configured"] is True
    assert data["providers"]["anthropic"]["status"] == "operational"

@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
def test_api_status_major_outage(mock_sse, mock_db, client):
    """Test /api/status when database or SSE is down, resulting in major_outage status."""
    mock_db.return_value = (False, {"error": "connection refused"})
    mock_sse.return_value = (True, {"ok": True})
    
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "major_outage"
    assert data["database"] == "down"
