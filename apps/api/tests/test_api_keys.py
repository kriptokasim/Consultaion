"""
Tests for API key management and authentication.

Patchset 37.0
"""

import pytest
from fastapi.testclient import TestClient

from api_key_utils import generate_api_key, verify_api_key
from models import APIKey, User


@pytest.fixture
def client():
    """Test client for making API requests."""
    from main import app
    return TestClient(app)



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


def test_create_and_verify_api_key(db_session):
    """Test creating and verifying an API key in the database."""
    # Create a user
    user = User(
        email="test@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Generate and store a key
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    
    # Verify the key
    assert api_key.prefix == prefix
    assert api_key.name == "Test Key"
    assert api_key.revoked is False
    assert verify_api_key(full_key, api_key.hashed_key)


def test_revoke_api_key(db_session):
    """Test revoking an API key."""
    # Create a user and key
    user = User(
        email="test2@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    
    # Revoke the key
    api_key.revoked = True
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    
    assert api_key.revoked is True


def test_api_key_last_used_tracking(db_session):
    """Test that last_used_at can be updated."""
    from datetime import datetime, timezone
    
    # Create a user and key
    user = User(
        email="test3@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    
    full_key, prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        user_id=user.id,
        name="Test Key",
        prefix=prefix,
        hashed_key=hashed_key,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    
    assert api_key.last_used_at is None
    
    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    
    assert api_key.last_used_at is not None


def test_create_api_key_returns_secret_on_success(client, db_session):
    """Test that POST /keys returns the secret on successful creation."""
    from auth import hash_password
    
    # Create a user
    user = User(
        email="secret_test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Login to get auth cookie
    login_response = client.post(
        "/auth/login",
        json={"email": "secret_test@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Create API key
    response = client.post(
        "/keys",
        json={"name": "Test Key"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert data["secret"].startswith("pk_")
    assert len(data["secret"]) > 40
    assert data["name"] == "Test Key"
    assert "id" in data
    assert "prefix" in data


def test_create_api_key_audit_log_failure_does_not_rollback(client, db_session, monkeypatch):
    """Test that audit log failure doesn't prevent API key creation."""
    from auth import hash_password
    from sqlalchemy.exc import SQLAlchemyError
    
    # Create a user
    user = User(
        email="audit_fail_test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Login to get auth cookie
    login_response = client.post(
        "/auth/login",
        json={"email": "audit_fail_test@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Mock record_audit to raise an error
    def mock_record_audit(*args, **kwargs):
        raise SQLAlchemyError("Simulated audit log failure")
    
    import routes.api_keys
    monkeypatch.setattr(routes.api_keys, "record_audit", mock_record_audit)
    
    # Create API key - should succeed despite audit failure
    response = client.post(
        "/keys",
        json={"name": "Test Key With Audit Failure"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert data["secret"].startswith("pk_")
    
    # Verify the key was actually created in the database
    from sqlmodel import select
    stmt = select(APIKey).where(APIKey.user_id == user.id)
    created_key = db_session.exec(stmt).first()
    
    assert created_key is not None
    assert created_key.name == "Test Key With Audit Failure"
    assert created_key.revoked is False

