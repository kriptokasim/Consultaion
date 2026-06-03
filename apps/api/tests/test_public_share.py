import pytest
from fastapi.testclient import TestClient
from models import Debate
from sqlmodel import Session
from auth import create_access_token, hash_password, COOKIE_NAME
from models import User

def test_owner_can_toggle_share(authenticated_client: TestClient, db_session: Session):
    # Create a debate
    create_res = authenticated_client.post(
        "/debates",
        json={
            "prompt": "Test debate for sharing",
            "mode": "arena"
        }
    )
    assert create_res.status_code == 200
    debate_id = create_res.json()["id"]

    # Toggle share to public
    share_res = authenticated_client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True}
    )
    assert share_res.status_code == 200
    assert share_res.json()["is_public"] is True

    # Check DB
    debate = db_session.get(Debate, debate_id)
    assert debate.config.get("is_public") is True

    # Toggle share back to private
    share_res = authenticated_client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": False}
    )
    assert share_res.status_code == 200
    
    # Check DB
    db_session.refresh(debate)
    assert debate.config.get("is_public") is False

def test_unauthenticated_cannot_toggle_share(client: TestClient, authenticated_client: TestClient):
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Test prompt that is long enough", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    client.cookies.delete(COOKIE_NAME)
    share_res = client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True}
    )
    assert share_res.status_code == 401

def test_non_owner_cannot_toggle_share(client: TestClient, authenticated_client: TestClient, db_session: Session):
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Test prompt that is long enough", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Create a second user
    user2 = User(email="second@example.com", password_hash=hash_password("password"))
    db_session.add(user2)
    db_session.commit()
    token2 = create_access_token(user_id=user2.id, email=user2.email, role=user2.role)
    
    client.cookies.set(COOKIE_NAME, token2)
    share_res = client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True}
    )
    assert share_res.status_code == 403
    client.cookies.delete(COOKIE_NAME)

def test_public_read_only_access(client: TestClient, authenticated_client: TestClient, db_session: Session):
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Test public access that is long enough", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Save token so we can restore it for authenticated_client
    auth_token = client.cookies.get(COOKIE_NAME)

    client.cookies.delete(COOKIE_NAME)
    # Initially private, unauth should get 404 to avoid ID enumeration
    get_res = client.get(f"/debates/{debate_id}")
    assert get_res.status_code == 404

    # Restore token and make public
    client.cookies.set(COOKIE_NAME, auth_token)
    share_res = authenticated_client.post(f"/debates/{debate_id}/share", json={"is_public": True})
    assert share_res.status_code == 200

    # Unauth can read details
    client.cookies.delete(COOKIE_NAME)
    get_res = client.get(f"/debates/{debate_id}")
    assert get_res.status_code == 200
    assert get_res.json()["prompt"] == "Test public access that is long enough"

    # Unauth can read timeline
    timeline_res = client.get(f"/debates/{debate_id}/timeline")
    assert timeline_res.status_code == 200

    # Unauth CANNOT mutate (e.g. export)
    export_res = client.post(f"/debates/{debate_id}/export")
    assert export_res.status_code == 401


# ---------------------------------------------------------------------------
# P0: Public DTO serialization tests
# ---------------------------------------------------------------------------

def test_public_debate_returns_safe_dto(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """Public run GET must return PublicDebateDTO — no config, routing_meta, panel_config, user_id."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Public DTO test prompt here", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Make public
    authenticated_client.post(f"/debates/{debate_id}/share", json={"is_public": True})

    # Fetch as unauthenticated user
    client.cookies.delete(COOKIE_NAME)
    get_res = client.get(f"/debates/{debate_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    # Verify public fields are present
    assert data["id"] == debate_id
    assert data["prompt"] == "Public DTO test prompt here"
    assert data["is_public"] is True
    assert "status" in data
    assert "mode" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify sensitive fields are ABSENT
    assert "config" not in data, "config must not leak to public"
    assert "routing_meta" not in data, "routing_meta must not leak to public"
    assert "panel_config" not in data, "panel_config must not leak to public"
    assert "user_id" not in data, "user_id must not leak to public"
    assert "team_id" not in data, "team_id must not leak to public"
    assert "runner_id" not in data, "runner_id must not leak to public"
    assert "run_attempt" not in data, "run_attempt must not leak to public"
    assert "engine_version" not in data, "engine_version must not leak to public"


def test_owner_debate_returns_full_dto(authenticated_client: TestClient, db_session: Session):
    """Owner GET must return PrivateDebateDTO — full data."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Owner DTO test prompt", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    get_res = authenticated_client.get(f"/debates/{debate_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    # Owner gets full fields
    assert data["id"] == debate_id
    assert "config" in data
    assert "user_id" in data


def test_public_events_are_filtered(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """Public event endpoint must strip internal metadata from events."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Events filter test prompt here", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Make public
    authenticated_client.post(f"/debates/{debate_id}/share", json={"is_public": True})

    # Fetch events as unauthenticated user
    client.cookies.delete(COOKIE_NAME)
    events_res = client.get(f"/debates/{debate_id}/events")
    assert events_res.status_code == 200

    # If there are events, verify no internal fields leak
    data = events_res.json()
    items = data.get("items", data if isinstance(data, list) else [])
    for event in items:
        assert "seat_id" not in event, "seat_id must not leak to public events"
        assert "meta" not in event, "meta must not leak to public events"
        assert "debug" not in event, "debug must not leak to public events"
        assert "error_details" not in event, "error_details must not leak to public events"


# ---------------------------------------------------------------------------
# P0: Mutation hardening tests
# ---------------------------------------------------------------------------

def test_unauthenticated_cannot_start_debate(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """POST /debates/{id}/start must require authentication — not optional."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Start hardening test prompt", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Make public so access isn't the issue
    authenticated_client.post(f"/debates/{debate_id}/share", json={"is_public": True})

    # Try to start as unauthenticated user — must be rejected
    client.cookies.delete(COOKIE_NAME)
    start_res = client.post(f"/debates/{debate_id}/start")
    assert start_res.status_code == 401, "Unauthenticated user must not start debates"


def test_non_owner_cannot_start_debate(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """POST /debates/{id}/start must require owner — not just any authenticated user."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Non-owner start test prompt", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Create second user
    user2 = User(email="starttest@example.com", password_hash=hash_password("password"))
    db_session.add(user2)
    db_session.commit()
    token2 = create_access_token(user_id=user2.id, email=user2.email, role=user2.role)

    client.cookies.set(COOKIE_NAME, token2)
    start_res = client.post(f"/debates/{debate_id}/start")
    # Should be 403 (permission denied) — not 200 or 404
    assert start_res.status_code in (403, 422), "Non-owner must not start debates"
    client.cookies.delete(COOKIE_NAME)


def test_unauthenticated_cannot_access_report(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """GET /debates/{id}/report must require authentication."""
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Report access test prompt here", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]

    # Make public so it's not just 404
    authenticated_client.post(f"/debates/{debate_id}/share", json={"is_public": True})

    client.cookies.delete(COOKIE_NAME)
    report_res = client.get(f"/debates/{debate_id}/report")
    assert report_res.status_code == 401, "Unauthenticated user must not access reports"


# ---------------------------------------------------------------------------
# P0: Text safety tests
# ---------------------------------------------------------------------------

def test_sanitize_public_text():
    """Verify text safety utilities redact sensitive content."""
    from utils.text_safety import sanitize_public_text, contains_sensitive_pattern, truncate_public_preview

    # API keys
    assert contains_sensitive_pattern("my key is sk-1234567890abcdefghijklmno")
    assert "[REDACTED_API_KEY]" in sanitize_public_text("Use key sk-1234567890abcdefghijklmno")

    # Emails
    assert contains_sensitive_pattern("email me at test@example.com")
    assert "[REDACTED_EMAIL]" in sanitize_public_text("email me at test@example.com")

    # JWT tokens
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiMSJ9.signature123456"
    assert contains_sensitive_pattern(jwt)
    assert "[REDACTED_TOKEN]" in sanitize_public_text(jwt)

    # Clean text passes through
    clean = "What is the meaning of life?"
    assert not contains_sensitive_pattern(clean)
    assert sanitize_public_text(clean) == clean

    # Truncation with sensitive content
    assert truncate_public_preview("My key is sk-1234567890abcdefghijklmno") == "Shared Arena Run"
    assert truncate_public_preview("What is the meaning of life?") == "What is the meaning of life?"
    assert truncate_public_preview("A" * 100) == "A" * 57 + "..."
