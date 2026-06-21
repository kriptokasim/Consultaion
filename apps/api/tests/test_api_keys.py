"""
Tests for API key management and authentication.

Patchset 37.0
"""

import pytest
from api_key_utils import generate_api_key, verify_api_key
from fastapi.testclient import TestClient
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


def test_api_key_expiration(client, db_session):
    """Test creating an expired API key and using it for auth (should fail)."""
    from datetime import datetime, timedelta, timezone

    from auth import hash_password
    
    # Create a user
    user = User(
        email="expiry_test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create an API key that is already expired (expires_at in past)
    from api_key_utils import generate_api_key
    full_key, prefix, hashed_key = generate_api_key()
    expired_key = APIKey(
        user_id=user.id,
        name="Expired Key",
        prefix=prefix,
        hashed_key=hashed_key,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        revoked=False,
    )
    db_session.add(expired_key)
    db_session.commit()
    db_session.refresh(expired_key)
    
    # Try calling a route using this expired API key
    response = client.get(
        "/test-api-key-auth",
        headers={"Authorization": f"Bearer {full_key}"}
    )
    assert response.status_code == 401
    
    # Verify audit log for expired key failure
    from models import AuditLog
    from sqlmodel import select
    logs_expired = db_session.exec(select(AuditLog).where(
        AuditLog.action == "api_key_auth_failed"
    )).all()
    # Check that at least one of these failed due to expiration
    expired_logs = [log for log in logs_expired if log.meta.get("reason") == "expired"]
    assert len(expired_logs) == 1
    assert logs_expired[0].meta["reason"] == "expired"
    assert logs_expired[0].meta["prefix"] == prefix
    
    # Create a key that is valid (expires_at in future)
    full_key2, prefix2, hashed_key2 = generate_api_key()
    valid_key = APIKey(
        user_id=user.id,
        name="Valid Key",
        prefix=prefix2,
        hashed_key=hashed_key2,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        revoked=False,
    )
    db_session.add(valid_key)
    db_session.commit()
    db_session.refresh(valid_key)
    
    # Try calling a route using this valid API key
    response2 = client.get(
        "/test-api-key-auth",
        headers={"Authorization": f"Bearer {full_key2}"}
    )
    print(f"DEBUG RESPONSE: {response2.status_code} - {response2.text}")
    assert response2.status_code == 200

    # Attempt using valid prefix but invalid secret
    response_invalid_secret = client.get(
        "/test-api-key-auth",
        headers={"Authorization": f"Bearer {prefix2}invalidsecret"}
    )
    assert response_invalid_secret.status_code == 401
    
    # Verify audit log for invalid secret failure
    stmt_invalid = select(AuditLog).where(
        AuditLog.user_id == user.id,
        AuditLog.action == "api_key_auth_failed"
    ).order_by(AuditLog.created_at.desc())
    logs_invalid = db_session.exec(stmt_invalid).all()
    assert len(logs_invalid) >= 2
    assert logs_invalid[0].meta["reason"] == "invalid_secret"
    assert logs_invalid[0].meta["prefix"] == prefix2

    # Revoke valid_key and try again
    valid_key.revoked = True
    db_session.add(valid_key)
    db_session.commit()
    
    response_revoked = client.get(
        "/test-api-key-auth",
        headers={"Authorization": f"Bearer {full_key2}"}
    )
    assert response_revoked.status_code == 401
    
    # Verify audit log for revoked key failure
    stmt_revoked = select(AuditLog).where(
        AuditLog.user_id == user.id,
        AuditLog.action == "api_key_auth_failed"
    ).order_by(AuditLog.created_at.desc())
    logs_revoked = db_session.exec(stmt_revoked).all()
    assert len(logs_revoked) >= 3
    assert logs_revoked[0].meta["reason"] == "revoked"
    assert logs_revoked[0].meta["prefix"] == prefix2


@pytest.mark.asyncio
async def test_api_key_rotation_reminder(db_session):
    """Test that API keys expiring in <= 7 days trigger reminders."""
    from auth import hash_password
    from orchestrator_cleanup import check_api_key_rotations

    # Create a user
    user = User(
        email="rotation_test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    
    # 1. Key expiring in 3 days (should trigger reminder)
    full_key1, prefix1, hashed_key1 = generate_api_key()
    key_expiring_soon = APIKey(
        user_id=user.id,
        name="Expiring Soon Key",
        prefix=prefix1,
        hashed_key=hashed_key1,
        expires_at=now + timedelta(days=3),
        revoked=False,
        rotation_reminder_sent=False,
    )
    
    # 2. Key expiring in 10 days (should NOT trigger reminder)
    full_key2, prefix2, hashed_key2 = generate_api_key()
    key_expiring_later = APIKey(
        user_id=user.id,
        name="Expiring Later Key",
        prefix=prefix2,
        hashed_key=hashed_key2,
        expires_at=now + timedelta(days=10),
        revoked=False,
        rotation_reminder_sent=False,
    )
    
    # 3. Expired key (should NOT trigger reminder as now > expires_at)
    full_key3, prefix3, hashed_key3 = generate_api_key()
    key_already_expired = APIKey(
        user_id=user.id,
        name="Already Expired Key",
        prefix=prefix3,
        hashed_key=hashed_key3,
        expires_at=now - timedelta(days=1),
        revoked=False,
        rotation_reminder_sent=False,
    )
    
    db_session.add(key_expiring_soon)
    db_session.add(key_expiring_later)
    db_session.add(key_already_expired)
    db_session.commit()
    
    # Run the check
    reminded_count = await check_api_key_rotations()
    assert reminded_count == 1
    
    # Refresh and assert
    db_session.refresh(key_expiring_soon)
    db_session.refresh(key_expiring_later)
    db_session.refresh(key_already_expired)
    
    assert key_expiring_soon.rotation_reminder_sent is True
    assert key_expiring_later.rotation_reminder_sent is False
    assert key_already_expired.rotation_reminder_sent is False


