"""Tests for LLM action guard."""

from unittest.mock import MagicMock, patch

import pytest
from exceptions import PermissionError, RateLimitError, ValidationError
from guards.llm_action_guard import (
    ACTION_RATE_LIMITS,
    _user_last_action,
    require_llm_action_allowed,
)
from models import User


def _make_user(**kwargs):
    user = MagicMock(spec=User)
    user.id = kwargs.get("id", "user-1")
    user.is_active = kwargs.get("is_active", True)
    user.hosted_credits_limit = kwargs.get("hosted_credits_limit", 10)
    user.hosted_credits_used = kwargs.get("hosted_credits_used", 0)
    user.role = "user"
    return user


def _make_session():
    session = MagicMock()
    session.get.return_value = None
    return session


class TestRequireLLMActionAllowed:
    def setup_method(self):
        _user_last_action.clear()

    @patch("guards.llm_action_guard.increment_ip_bucket", return_value=(True, 0))
    def test_inactive_user_raises(self, _mock_bucket):
        user = _make_user(is_active=False)
        session = _make_session()
        with pytest.raises(PermissionError, match="not active"):
            require_llm_action_allowed(user=user, action="oracle_session", session=session)

    @patch("guards.llm_action_guard.increment_ip_bucket", return_value=(True, 0))
    def test_credits_exhausted_raises(self, _mock_bucket):
        user = _make_user(hosted_credits_used=10, hosted_credits_limit=10)
        session = _make_session()
        with pytest.raises(ValidationError, match="credits exhausted"):
            require_llm_action_allowed(user=user, action="oracle_session", session=session)

    @patch("guards.llm_action_guard.increment_ip_bucket", return_value=(True, 0))
    def test_consume_credit_on_success(self, _mock_bucket):
        user = _make_user(hosted_credits_used=5, hosted_credits_limit=10)
        session = _make_session()
        require_llm_action_allowed(user=user, action="oracle_session", session=session)
        assert user.hosted_credits_used == 6
        session.add.assert_called_once_with(user)
        session.commit.assert_called_once()

    @patch("guards.llm_action_guard.increment_ip_bucket", return_value=(True, 0))
    def test_cooldown_enforced(self, _mock_bucket):
        user = _make_user()
        session = _make_session()
        # First call succeeds
        require_llm_action_allowed(user=user, action="oracle_session", session=session)
        # Second call immediately should hit cooldown
        with pytest.raises(RateLimitError, match="wait"):
            require_llm_action_allowed(user=user, action="oracle_session", session=session)

    @patch("guards.llm_action_guard.increment_ip_bucket", return_value=(True, 0))
    def test_different_actions_not_cooldown(self, _mock_bucket):
        user = _make_user()
        session = _make_session()
        require_llm_action_allowed(user=user, action="oracle_session", session=session)
        # Different action should not be blocked by cooldown
        require_llm_action_allowed(user=user, action="redteam_session", session=session)

    def test_action_rate_limits_defined(self):
        expected_actions = [
            "arena_run", "debate_run", "oracle_session", "oracle_fork",
            "redteam_session", "challenge_round", "divergence_recompute", "voting_prediction",
        ]
        for action in expected_actions:
            assert action in ACTION_RATE_LIMITS
            window, max_req = ACTION_RATE_LIMITS[action]
            assert window > 0
            assert max_req > 0
