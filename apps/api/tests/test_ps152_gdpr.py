"""Tests for PS152: GDPR deletion, account erasure, credit guard, and auth helpers."""

import secrets
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from auth import hash_password, verify_password
from models import User, utcnow


def _make_user(**overrides) -> User:
    """Create a minimal User for testing."""
    defaults = {
        "id": str(secrets.token_hex(8)),
        "email": f"test-{secrets.token_hex(4)}@example.com",
        "password_hash": hash_password("test-password-123"),
        "role": "user",
    }
    defaults.update(overrides)
    return User(**defaults)


# ── Track A: deletion_requested_at field ────────────────────────────


class TestDeletionRequestedAtField:
    """A1: User model has deletion_requested_at field."""

    def test_user_has_field(self):
        user = _make_user()
        assert hasattr(user, "deletion_requested_at")
        assert user.deletion_requested_at is None

    def test_field_settable(self):
        now = utcnow()
        user = _make_user()
        user.deletion_requested_at = now
        assert user.deletion_requested_at == now


# ── Track B: GDPR request, cancel, processing ──────────────────────


class TestGdprDeletionRequest:
    """B1-B3: Deletion request keeps user active, cancellation works."""

    def test_request_sets_timestamp_keeps_active(self):
        """B2: Deletion request must NOT deactivate the user."""
        from gdpr.service import create_deletion_request

        db = MagicMock()
        user = _make_user()
        db.get.return_value = user

        result = create_deletion_request(db, user.id)

        assert result["status"] == "scheduled"
        assert user.deletion_requested_at is not None
        assert user.is_active is True  # B2: must remain active
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_duplicate_request_idempotent(self):
        """B1: Duplicate request returns already_requested."""
        from gdpr.service import create_deletion_request

        db = MagicMock()
        now = utcnow()
        user = _make_user(deletion_requested_at=now)
        db.get.return_value = user

        result = create_deletion_request(db, user.id)
        assert result["status"] == "already_requested"

    def test_cancellation_clears_timestamp(self):
        """B3: Cancellation clears deletion_requested_at and keeps active."""
        from gdpr.service import cancel_deletion_request

        db = MagicMock()
        now = utcnow()
        user = _make_user(deletion_requested_at=now)
        db.get.return_value = user

        result = cancel_deletion_request(db, user.id)

        assert result["status"] == "cancelled"
        assert user.deletion_requested_at is None
        assert user.is_active is True

    def test_cancellation_no_pending(self):
        from gdpr.service import cancel_deletion_request

        db = MagicMock()
        user = _make_user()
        db.get.return_value = user

        result = cancel_deletion_request(db, user.id)
        assert result["status"] == "no_pending_request"


# ── Track C: Shared account erasure ─────────────────────────────────


class TestAccountErasure:
    """C1-C2: Shared erasure service produces correct result."""

    def test_erasure_sets_deleted_at_and_anonymizes(self):
        from services.account_erasure import erase_user_account

        db = MagicMock()
        user = _make_user()

        # Mock query execution — needs objects with .all() method
        empty_result = MagicMock()
        empty_result.all.return_value = []
        db.exec.return_value = empty_result

        result = erase_user_account(db, user, reason="test")

        assert result.user_id == user.id
        assert result.debates_anonymized == 0
        assert user.deleted_at is not None
        assert user.is_active is False
        assert user.deletion_requested_at is None
        assert user.email.startswith("deleted+")
        assert user.email.endswith("@invalid.local")
        assert user.display_name is None
        assert user.avatar_url is None
        assert user.bio is None
        assert user.timezone is None
        assert user.email_summaries_enabled is False
        # Password hash must remain valid and non-null
        assert user.password_hash is not None
        assert verify_password("anything-else-wont-match", user.password_hash) is False
        # Reset lockout
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.last_failed_login_at is None

    def test_erasure_does_not_rely_on_fake_attributes(self):
        """No fake name/google_id/anonymized_at attributes used."""
        from services.account_erasure import erase_user_account

        db = MagicMock()
        user = _make_user()
        empty_result = MagicMock()
        empty_result.all.return_value = []
        db.exec.return_value = empty_result

        erase_user_account(db, user, reason="test")

        # Verify we didn't try to set non-existent attributes
        assert not hasattr(user, "name") or user.name is not _make_user.__defaults__[0]
        assert not hasattr(user, "google_id")
        assert not hasattr(user, "anonymized_at")


# ── Track E: Multi-worker credit guard ──────────────────────────────


class TestCreditGuard:
    """E1: DB-level atomic UPDATE for credit consumption."""

    def test_in_memory_lock_is_process_local(self):
        """E2: Local lock exists but is documented as process-local."""
        from guards.llm_action_guard import _get_user_lock

        lock1 = _get_user_lock("user-1")
        lock2 = _get_user_lock("user-1")
        assert lock1 is lock2  # same object within process

        lock3 = _get_user_lock("user-2")
        assert lock1 is not lock3  # different users get different locks


# ── Track D: GDPR export uses real fields ───────────────────────────


class TestGdprExport:
    """D: Export uses actual User fields, not non-existent name."""

    def test_export_uses_real_fields(self):
        from gdpr.service import export_user_data

        db = MagicMock()
        user = _make_user(display_name="Test User", bio="Hello")
        db.get.return_value = user
        empty_result = MagicMock()
        empty_result.all.return_value = []
        db.exec.return_value = empty_result

        export = export_user_data(db, user.id)

        profile = export["profile"]
        assert profile["id"] == user.id
        assert profile["email"] == user.email
        assert profile["display_name"] == "Test User"
        assert profile["bio"] == "Hello"
        assert "name" not in profile
        # Ensure password hash is NOT exported
        assert "password_hash" not in profile


# ── Track F: Runtime config helpers ─────────────────────────────────


class TestRuntimeConfigHelpers:
    """F1: WEB_APP_ORIGIN is accessed at runtime, not snapshot."""

    def test_get_web_app_origin_reads_settings(self):
        from routes.auth import get_web_app_origin

        from config import settings

        with patch.object(settings, "WEB_APP_ORIGIN", "https://example.com"):
            assert get_web_app_origin() == "https://example.com"

    def test_get_web_app_origin_strips_trailing_slash(self):
        from routes.auth import get_web_app_origin

        from config import settings

        with patch.object(settings, "WEB_APP_ORIGIN", "https://example.com/"):
            assert get_web_app_origin() == "https://example.com"

    def test_get_web_app_origin_raises_on_missing(self):
        from routes.auth import get_web_app_origin

        from config import settings

        with patch.object(settings, "WEB_APP_ORIGIN", None):
            with pytest.raises(ValueError):
                get_web_app_origin()


# ── Audit follow-up: transaction and complete erasure ───────────────


class TestScheduledDeletionTransactions:
    def test_processing_commits_outer_transaction(self):
        from gdpr.service import process_scheduled_deletions

        db = MagicMock()
        user = _make_user(deletion_requested_at=utcnow() - timedelta(days=31))
        pending = MagicMock()
        pending.all.return_value = [user]
        db.exec.return_value = pending
        savepoint = MagicMock()
        db.begin_nested.return_value = savepoint

        with patch("services.account_erasure.erase_user_account") as erase:
            result = process_scheduled_deletions(db)

        assert result == {"processed_count": 1, "failed_count": 0}
        erase.assert_called_once_with(db, user, reason="gdpr_scheduled")
        savepoint.commit.assert_called_once()
        db.commit.assert_called_once()

    def test_outer_commit_failure_rolls_back(self):
        from gdpr.service import process_scheduled_deletions

        db = MagicMock()
        pending = MagicMock()
        pending.all.return_value = []
        db.exec.return_value = pending
        db.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            process_scheduled_deletions(db)

        db.rollback.assert_called_once()


class TestCompleteAccountErasure:
    def test_recursive_pii_scrubber_handles_dicts_and_lists(self):
        from services.account_erasure import _scrub_pii

        value = {
            "context": {
                "items": [
                    {"email": "person@example.com"},
                    {"nested": {"ip_address": "203.0.113.8"}},
                ]
            },
            "safe": "keep",
        }

        assert _scrub_pii(value) == {
            "context": {
                "items": [
                    {"email": "[REDACTED]"},
                    {"nested": {"ip_address": "[REDACTED]"}},
                ]
            },
            "safe": "keep",
        }

    def test_coding_agent_records_are_in_erasure_plan(self):
        from services.account_erasure import erase_user_account

        db = MagicMock()
        user = _make_user()
        empty_result = MagicMock()
        empty_result.all.return_value = []
        db.exec.return_value = empty_result

        erase_user_account(db, user, reason="test")

        statements = "\n".join(str(call.args[0]) for call in db.execute.call_args_list)
        assert "coding_patch_artifact" in statements
        assert "coding_lane_result" in statements
        assert "coding_turn" in statements
        assert "DELETE FROM coding_run" in statements
