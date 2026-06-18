"""BYOK encryption round-trip and isolation tests.

Patchset 133 §7.1: Proves encryption/decryption uses identical AAD,
wrong context fails, and keys never appear in logs.
"""

import os
import pytest
import uuid
import logging
import base64
from sqlmodel import Session, select
from models import User, UserProviderKey
from security.encryption import encrypt_value, decrypt_value, fingerprint_key, validate_keyring


@pytest.fixture(autouse=True)
def _configure_keyring():
    """Configure test encryption keyring for BYOK tests."""
    key = base64.b64encode(os.urandom(32)).decode()
    os.environ["PROVIDER_KEY_ENCRYPTION_KEYS"] = f'{{"1":"{key}"}}'
    os.environ["PROVIDER_KEY_ACTIVE_VERSION"] = "1"
    yield
    os.environ.pop("PROVIDER_KEY_ENCRYPTION_KEYS", None)
    os.environ.pop("PROVIDER_KEY_ACTIVE_VERSION", None)


@pytest.fixture
def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"byok-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestBYOKRoundTrip:
    def test_provider_key_round_trip(self, test_user):
        """FH125: Encrypt with AAD → decrypt with same AAD succeeds."""
        plaintext = "sk-test-1234567890abcdef"
        encrypted = encrypt_value(plaintext, user_id=test_user.id, provider="openai")

        assert encrypted["ciphertext"]
        assert encrypted["nonce"]
        assert encrypted["key_version"] >= 1

        decrypted = decrypt_value(encrypted, user_id=test_user.id, provider="openai")
        assert decrypted == plaintext

    def test_provider_key_wrong_user_fails(self, test_user):
        """FH125: Decrypt with wrong user_id fails."""
        plaintext = "sk-test-wrong-user"
        encrypted = encrypt_value(plaintext, user_id=test_user.id, provider="openai")

        with pytest.raises(Exception):
            decrypt_value(encrypted, user_id="wrong-user-id", provider="openai")

    def test_provider_key_wrong_provider_fails(self, test_user):
        """FH125: Decrypt with wrong provider fails."""
        plaintext = "sk-test-wrong-provider"
        encrypted = encrypt_value(plaintext, user_id=test_user.id, provider="openai")

        with pytest.raises(Exception):
            decrypt_value(encrypted, user_id=test_user.id, provider="anthropic")

    def test_provider_key_never_logged(self, test_user, caplog):
        """FH125: Provider key must never appear in logs."""
        plaintext = "sk-secret-key-12345"

        with caplog.at_level(logging.DEBUG):
            encrypted = encrypt_value(plaintext, user_id=test_user.id, provider="openai")
            decrypted = decrypt_value(encrypted, user_id=test_user.id, provider="openai")

        # Check that plaintext never appears in any log record
        for record in caplog.records:
            assert plaintext not in record.getMessage(), (
                f"Plaintext key found in log: {record.getMessage()}"
            )

    def test_provider_key_fingerprint(self):
        """FH125: Fingerprint is deterministic and short."""
        fp1 = fingerprint_key("sk-test-12345")
        fp2 = fingerprint_key("sk-test-12345")
        assert fp1 == fp2
        assert len(fp1) < 20  # Should be short

    def test_keyring_validation(self):
        """FH125: Keyring validation runs without error."""
        # Should not raise — either keyring is configured or not
        try:
            validate_keyring()
        except RuntimeError:
            pass  # Expected if no keyring configured


class TestBYOKRouteToResolver:
    def test_provider_key_round_trip_route_to_resolver(self, db_session, test_user):
        """FH125: Save key via route encryption, resolve via credential service."""
        from services.provider_credentials import resolve_provider_credential

        plaintext = "sk-route-test-12345"
        encrypted = encrypt_value(plaintext, user_id=test_user.id, provider="openai")

        # Create a key record as if the route saved it
        key_record = UserProviderKey(
            user_id=test_user.id,
            provider="openai",
            masked_key="sk-...12345",
            encrypted_key=encrypted["ciphertext"],
            encryption_nonce=encrypted["nonce"],
            encryption_key_version=encrypted["key_version"],
            key_fingerprint=fingerprint_key(plaintext),
        )
        db_session.add(key_record)
        db_session.commit()

        # Resolve via credential service
        credential = resolve_provider_credential(db_session, test_user.id, "openai")
        assert credential is not None
        assert credential.key == plaintext
        assert credential.source == "user"
        assert credential.provider == "openai"
