"""
Tests for config validation (Patchset 29.0).

Tests that production environments enforce secret configuration
and local environments log warnings without blocking.
"""

import pytest
import os
from unittest.mock import patch

from config import AppSettings


def test_production_requires_jwt_secret():
    """Production must have non-default JWT_SECRET."""
    with pytest.raises(ValueError, match="JWT_SECRET must be set"):
        AppSettings(
            ENV="production",
            JWT_SECRET="change_me_in_prod",
        )


def test_production_requires_long_jwt_secret():
    """Production JWT_SECRET must be at least 32 characters."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        AppSettings(
            ENV="production",
            JWT_SECRET="short",
        )


def test_production_stripe_webhook_verify_requires_secret():
    """Stripe webhook verification requires secret in production."""
    with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET required"):
        AppSettings(
            ENV="production",
            JWT_SECRET="a" * 32,  # Valid JWT secret
            STRIPE_WEBHOOK_VERIFY=True,
            STRIPE_WEBHOOK_SECRET=None,
        )


def test_production_require_real_llm_needs_provider():
    """REQUIRE_REAL_LLM=1 requires at least one provider key."""
    with pytest.raises(ValueError, match="At least one provider API key"):
        AppSettings(
            ENV="production",
            JWT_SECRET="a" * 32,
            REQUIRE_REAL_LLM=True,
            REDIS_URL="redis://localhost",
            STRIPE_WEBHOOK_VERIFY=False,  # Disable to test LLM validation only
            OPENAI_API_KEY=None,
            ANTHROPIC_API_KEY=None,
            GEMINI_API_KEY=None,
            GOOGLE_API_KEY=None,
        )


def test_production_accepts_valid_config():
    """Production should accept properly configured secrets."""
    settings = AppSettings(
        ENV="production",
        JWT_SECRET="a" * 32,
        OPENAI_API_KEY="sk-test",
        REQUIRE_REAL_LLM=True,
        REDIS_URL="redis://localhost",
        STRIPE_WEBHOOK_VERIFY=False,  # Simplify test
    )
    
    assert settings.JWT_SECRET == "a" * 32
    assert not settings.IS_LOCAL_ENV


def test_local_env_allows_weak_secrets():
    """Local environment should allow weak secrets with warnings."""
    # Should not raise, only warn
    settings = AppSettings(
        ENV="local",
        JWT_SECRET="change_me_in_prod",
    )
    
    assert settings.IS_LOCAL_ENV
    assert settings.JWT_SECRET == "change_me_in_prod"


def test_local_env_with_stripe_verify_no_secret():
    """Local env should warn but not block on Stripe config."""
    settings = AppSettings(
        ENV="local",
        STRIPE_WEBHOOK_VERIFY=True,
        STRIPE_WEBHOOK_SECRET=None,
    )
    
    assert settings.IS_LOCAL_ENV


def test_development_env_is_local():
    """'development' should be treated as local."""
    settings = AppSettings(ENV="development")
    assert settings.IS_LOCAL_ENV


def test_test_env_is_local():
    """'test' should be treated as local."""
    settings = AppSettings(ENV="test")
    assert settings.IS_LOCAL_ENV
