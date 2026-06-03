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
