"""
Patchset 138 — Track D6: Schema extra-field hardening tests.

Verifies that AuthRequest and DebateUpdate reject unknown fields with 422.
"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-schema-tests")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")

import pytest
from auth import COOKIE_NAME
from database import init_db
from fastapi.testclient import TestClient
from main import app
from sse_backend import get_sse_backend

init_db()


@pytest.fixture(autouse=True)
def _setup_sse_backend():
    app.state.sse_backend = get_sse_backend()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return Bearer token headers for a test user (created via register endpoint)."""
    import uuid
    client = TestClient(app)
    email = f"authtest-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!"},
    )
    if resp.status_code == 201:
        token = client.cookies.get(COOKIE_NAME)
        if token:
            return {"Authorization": f"Bearer {token}"}
    # Fallback: create a raw token with a random user ID
    from auth import create_access_token
    token = create_access_token(
        user_id=f"test-user-{uuid.uuid4().hex[:8]}",
        email="fallback@example.com",
        role="user",
    )
    return {"Authorization": f"Bearer {token}"}


# ── AuthRequest extra="forbid" tests ──────────────────────────

def test_auth_request_accepts_valid_fields(client):
    """AuthRequest should accept email and password."""
    response = client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "SecurePass123!"},
    )
    # 201 = created (success) or 400 = already registered (still valid schema)
    assert response.status_code in (201, 400)


def test_auth_request_rejects_unknown_field(client):
    """AuthRequest should return 422 when unknown fields are present."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "admin": True,  # unknown field
        },
    )
    assert response.status_code == 422, (
        f"Expected 422 for extra field, got {response.status_code}: {response.text}"
    )
    data = response.json()
    # Pydantic v2 extra="forbid" surfaces the error as a validation error
    errors = data.get("detail") or data.get("errors") or []
    error_str = str(errors).lower() if errors else str(data).lower()
    assert any(
        keyword in error_str
        for keyword in ("extra", "forbid", "unexpected", "unknown")
    ), f"422 detail should mention the extra field: {data}"


def test_auth_request_rejects_multiple_unknown_fields(client):
    """Multiple unknown fields should also be rejected with 422."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "role": "superadmin",
            "api_key": "sk-xxx",
        },
    )
    assert response.status_code == 422


def test_auth_request_rejects_empty_extra_fields(client):
    """Extra fields with null/empty values should also be rejected."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "notes": None,
        },
    )
    assert response.status_code == 422


# ── DebateUpdate extra="forbid" tests ─────────────────────────

def test_debate_update_accepts_valid_fields(client, auth_headers):
    """DebateUpdate should accept team_id."""
    # Schema validation happens before debate lookup
    response = client.patch(
        "/debates/nonexistent-debate",
        json={"team_id": "some-team-id"},
        headers=auth_headers,
    )
    # 404 (debate not found) means schema passed — 422 would mean schema rejected valid data
    if response.status_code == 422:
        pytest.fail(f"422 for valid DebateUpdate schema: {response.text}")
    # Expected: 404 since the debate doesn't exist
    assert response.status_code == 404, f"Unexpected: {response.status_code}"


def test_debate_update_rejects_unknown_field(client, auth_headers):
    """DebateUpdate should return 422 when unknown fields are present."""
    response = client.patch(
        "/debates/nonexistent-debate",
        json={
            "team_id": "some-team-id",
            "title": "Hacked Title",  # unknown field
        },
        headers=auth_headers,
    )
    assert response.status_code == 422, (
        f"Expected 422 for extra field in DebateUpdate, got {response.status_code}: {response.text}"
    )


def test_debate_update_rejects_multiple_unknown_fields(client, auth_headers):
    """Multiple unknown fields should be rejected with 422."""
    response = client.patch(
        "/debates/nonexistent-debate",
        json={
            "team_id": "some-team-id",
            "title": "Hacked",
            "is_public": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
