"""
Patchset 103: Owner Override Tests

Tests for owner allowlist, plan override, and quota bypass.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")

sys.path.append(str(Path(__file__).resolve().parents[1]))


class FakeUser:
    """Minimal user-like object for testing."""
    def __init__(self, user_id: str, email: str, plan: str = "free", role: str = "user"):
        self.id = user_id
        self.email = email
        self.plan = plan
        self.role = role
        self.is_admin = False
        self.display_name = None
        self.avatar_url = None
        self.timezone = None
        self.is_active = True
        self.email_summaries_enabled = False


# ─── is_owner tests ───────────────────────────────────

def test_is_owner_returns_true_for_allowlisted_email():
    from security.owner import is_owner
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "admin@example.com,boss@corp.com"
    user = FakeUser("u1", "admin@example.com")
    assert is_owner(user) is True


def test_is_owner_returns_false_for_non_allowlisted():
    from security.owner import is_owner
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "admin@example.com"
    user = FakeUser("u2", "nobody@example.com")
    assert is_owner(user) is False


def test_is_owner_normalizes_case_and_whitespace():
    from security.owner import is_owner
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "  Admin@Example.COM  "
    user = FakeUser("u3", "admin@example.com")
    assert is_owner(user) is True


def test_is_owner_returns_false_for_none_user():
    from security.owner import is_owner
    assert is_owner(None) is False


def test_is_owner_returns_false_when_allowlist_empty():
    from security.owner import is_owner
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = ""
    user = FakeUser("u4", "admin@example.com")
    assert is_owner(user) is False


# ─── resolve_plan_for_user tests ─────────────────────

def test_resolve_plan_returns_owner_plan_for_owner():
    from plan_config import resolve_plan_for_user
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"
    settings._settings.OWNER_PLAN = "pro"
    user = FakeUser("u5", "owner@test.com", plan="free")
    assert resolve_plan_for_user(user) == "pro"


def test_resolve_plan_returns_user_plan_for_non_owner():
    from plan_config import resolve_plan_for_user
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"
    user = FakeUser("u6", "regular@test.com", plan="free")
    assert resolve_plan_for_user(user) == "free"


def test_resolve_plan_returns_free_for_anonymous():
    from plan_config import resolve_plan_for_user
    assert resolve_plan_for_user(None) == "free"


# ─── check_quota bypass tests ────────────────────────

def test_check_quota_bypasses_for_unlimited_owner():
    from usage_limits import check_quota
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"
    settings._settings.OWNER_UNLIMITED = True

    user = FakeUser("u7", "owner@test.com")

    # Should not raise even with absurd token requirement
    # We need a session mock since check_quota uses it
    mock_session = MagicMock()
    check_quota(mock_session, user, required_tokens=999_999_999)


def test_check_quota_enforces_for_non_owner():
    from usage_limits import check_quota, QuotaExceededError
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"
    settings._settings.OWNER_UNLIMITED = True

    user = FakeUser("u8", "regular@test.com", plan="free")

    mock_session = MagicMock()

    # Mock the usage to be at limit
    with patch("usage_limits.get_today_usage", return_value={"tokens_used": 99_999, "exports_used": 0}):
        try:
            check_quota(mock_session, user, required_tokens=999_999_999)
            assert False, "Should have raised QuotaExceededError"
        except QuotaExceededError:
            pass  # Expected


# ─── serialize_user tests ────────────────────────────

def test_serialize_user_includes_owner_fields():
    from routes.common import serialize_user
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"
    settings._settings.OWNER_PLAN = "pro"

    owner = FakeUser("u9", "owner@test.com")
    result = serialize_user(owner)

    assert result["is_owner"] is True
    assert result["plan"] == "pro"


def test_serialize_user_non_owner_fields():
    from routes.common import serialize_user
    from config import settings

    settings._settings.OWNER_EMAIL_ALLOWLIST = "owner@test.com"

    regular = FakeUser("u10", "regular@test.com", plan="free")
    result = serialize_user(regular)

    assert result["is_owner"] is False
    assert result["plan"] == "free"
