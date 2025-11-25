"""
Tests for API key management and authentication.

Patchset 37.0
"""

import pytest

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
