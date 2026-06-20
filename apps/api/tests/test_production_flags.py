import pytest
from config import AppSettings
from pydantic import ValidationError

from tests.utils import override_env


def test_production_config_validation_rules():
    """
    Assert that staging/production configurations raise errors when insecure flags are set.
    """
    # 1. USE_MOCK cannot be True in production
    with override_env({
        "ENV": "production",
        "USE_MOCK": "True",
        "FAST_DEBATE": "False",
        "STRIPE_WEBHOOK_INSECURE_DEV": "False",
        "REQUIRE_REAL_LLM": "True",
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        with pytest.raises(ValueError, match="USE_MOCK=True is not allowed"):
            AppSettings()

    # 2. REQUIRE_REAL_LLM cannot be False in production
    with override_env({
        "ENV": "production",
        "REQUIRE_REAL_LLM": "False",
        "USE_MOCK": "False",
        "FAST_DEBATE": "False",
        "STRIPE_WEBHOOK_INSECURE_DEV": "False",
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        with pytest.raises(ValueError, match="REQUIRE_REAL_LLM=False is not allowed"):
            AppSettings()

    # 3. ENABLE_SEC_HEADERS is coerced to True in production, even if passed as False
    with override_env({
        "ENV": "production",
        "ENABLE_SEC_HEADERS": "False",
        "REQUIRE_REAL_LLM": "True",
        "USE_MOCK": "False",
        "FAST_DEBATE": "False",
        "STRIPE_WEBHOOK_INSECURE_DEV": "False",
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        config = AppSettings()
        assert config.ENABLE_SEC_HEADERS is True

    # 4. ENABLE_CSRF cannot be False in production
    with override_env({
        "ENV": "production",
        "ENABLE_CSRF": "False",
        "REQUIRE_REAL_LLM": "True",
        "USE_MOCK": "False",
        "FAST_DEBATE": "False",
        "STRIPE_WEBHOOK_INSECURE_DEV": "False",
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        with pytest.raises(ValueError, match="ENABLE_CSRF=False is not allowed"):
            AppSettings()


def test_fast_debate_warning_in_production():
    """
    Assert that having FAST_DEBATE set in production/staging environments
    raises a validation error, preventing developers from running speed shortcuts in prod.
    """
    with override_env({
        "ENV": "production",
        "FAST_DEBATE": "True",
        "REQUIRE_REAL_LLM": "True",
        "USE_MOCK": "False",
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        with pytest.raises(ValidationError) as exc:
            AppSettings()
        assert "FAST_DEBATE=True is not allowed in staging or production" in str(exc.value)
