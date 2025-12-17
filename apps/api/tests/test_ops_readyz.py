from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from main import app  # Assuming app is in main.py


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz(client):
    """Healthz endpoint should always return 200."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
def test_readyz_success(mock_sse, mock_db, client):
    """Readyz should return 200 when all checks pass."""
    mock_db.return_value = (True, {"ping": True, "revision": "ok"})
    mock_sse.return_value = (True, {"backend": "memory", "ok": True})
    
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["details"]["db"]["ping"] is True


@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
def test_readyz_failure_db(mock_sse, mock_db, client):
    """Readyz should return 503 if DB check fails."""
    mock_db.return_value = (False, {"error": "connection failed"})
    mock_sse.return_value = (True, {"ok": True})
    
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "db" in response.json()["details"]


@patch("routes.ops.check_db_readiness")
@patch("routes.ops.check_sse_readiness")
def test_readyz_failure_sse(mock_sse, mock_db, client):
    """Readyz should return 503 if SSE check fails."""
    mock_db.return_value = (True, {"ok": True})
    mock_sse.return_value = (False, {"error": "redis down"})
    
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["details"]["sse"]["error"] == "redis down"
