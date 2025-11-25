"""
Tests for API key management and authentication.

Patchset 37.0
"""

import pytest
from fastapi.testclient import TestClient

from api_key_utils import generate_api_key, verify_api_key
from models import APIKey, User


def test_generate_api_key():
    """Test API key generation."""
    full_key, prefix, hashed_key = generate_api_key()
    
    # Check format
    assert full_key.startswith("pk_")
    assert prefix == full_key[:10]
    assert len(full_key) > 40  # Should be long enough
    
    # Verify hash works
    assert verify_api_key(full_key, hashed_key)
    assert not verify_api_key("wrong_key", hashed_key)


def test_list_api_keys_empty(client: TestClient, test_user: User, auth_headers: dict):
    """Test listing API keys when none exist."""
    response = client.get("/keys", headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json() == []


def test_create_api_key(client: TestClient, test_user: User, auth_headers: dict):
    """Test creating an API key."""
    response = client.post(
        "/keys",
        json={"name": "Test Key"},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "Test Key"
    assert "secret" in data
    assert data["secret"].startswith("pk_")
    assert "prefix" in data
    assert data["prefix"] == data["secret"][:10]
    assert "id" in data
    assert "created_at" in data


def test_create_api_key_without_name(client: TestClient, test_user: User, auth_headers: dict):
    """Test creating an API key without a name fails."""
    response = client.post(
        "/keys",
        json={"name": ""},
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "name_required" in response.json()["error"]["code"]


def test_list_api_keys(client: TestClient, test_user: User, auth_headers: dict, session):
    """Test listing API keys."""
    # Create a key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    session.commit()
    
    response = client.get("/keys", headers=auth_headers)
    
    assert response.status_code == 200
    keys = response.json()
    assert len(keys) == 1
    assert keys[0]["name"] == "Test Key"
    assert keys[0]["prefix"] == prefix
    assert "secret" not in keys[0]  # Secret should not be returned


def test_revoke_api_key(client: TestClient, test_user: User, auth_headers: dict, session):
    """Test revoking an API key."""
    # Create a key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    
    response = client.delete(f"/keys/{api_key.id}", headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json()["revoked"] is True
    
    # Verify key is revoked in database
    session.refresh(api_key)
    assert api_key.revoked is True


def test_revoke_nonexistent_key(client: TestClient, test_user: User, auth_headers: dict):
    """Test revoking a nonexistent key fails."""
    response = client.delete("/keys/nonexistent-id", headers=auth_headers)
    
    assert response.status_code == 404
    assert "not_found" in response.json()["error"]["code"]


def test_revoke_other_users_key(client: TestClient, test_user: User, auth_headers: dict, session):
    """Test that users cannot revoke other users' keys."""
    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash="hash",
    )
    session.add(other_user)
    session.commit()
    
    # Create a key for the other user
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=other_user.id,
        name="Other User's Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    
    response = client.delete(f"/keys/{api_key.id}", headers=auth_headers)
    
    assert response.status_code == 403
    assert "permission" in response.json()["error"]["code"]


def test_api_key_authentication(client: TestClient, test_user: User, session):
    """Test authenticating with an API key."""
    # Create a key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    session.commit()
    
    # Test with Authorization: Bearer header
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {full_key}"}
    )
    
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email
    
    # Test with X-API-Key header
    response = client.get(
        "/me",
        headers={"X-API-Key": full_key}
    )
    
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


def test_api_key_authentication_revoked(client: TestClient, test_user: User, session):
    """Test that revoked API keys cannot authenticate."""
    # Create a revoked key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="Revoked Key",
        prefix=prefix,
        hashed_key=hashed_key,
        revoked=True,
    )
    session.add(api_key)
    session.commit()
    
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {full_key}"}
    )
    
    assert response.status_code == 401


def test_api_key_authentication_invalid(client: TestClient):
    """Test that invalid API keys are rejected."""
    response = client.get(
        "/me",
        headers={"Authorization": "Bearer pk_invalid_key"}
    )
    
    assert response.status_code == 401


def test_api_key_last_used_updated(client: TestClient, test_user: User, session):
    """Test that last_used_at is updated when using an API key."""
    # Create a key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    
    assert api_key.last_used_at is None
    
    # Use the key
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {full_key}"}
    )
    
    assert response.status_code == 200
    
    # Check last_used_at was updated
    session.refresh(api_key)
    assert api_key.last_used_at is not None
