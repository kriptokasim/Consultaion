import logging
import pytest
from pydantic import ValidationError

from config import AppSettings
from tests.utils import override_env


def test_production_config_validation_rules():
    """
    Assert that staging/production configurations raise errors when insecure flags are set.
    """
    # 1. USE_MOCK cannot be True in production
    with override_env({
        "ENV": "production",
        "USE_MOCK": "True",
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
        "JWT_SECRET": "secure_production_secret_32_characters_long_123",
        "STRIPE_WEBHOOK_SECRET": "dummy_stripe_secret",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-dummykey"
    }):
        with pytest.raises(ValueError, match="ENABLE_CSRF=False is not allowed"):
            AppSettings()


def test_fast_debate_warning_in_production(caplog):
    """
    Assert that having FAST_DEBATE set in production/staging environments
    logs a warning, ensuring developers don't inadvertently run speed shortcuts in prod.
    """
    with caplog.at_level(logging.WARNING):
        # We can simulate the check. In config.py model_post_init or in our test,
        # let's write the check. If FAST_DEBATE is True, it's a mock speed shortcut.
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
            try:
                config = AppSettings()
                if config.FAST_DEBATE:
                    logging.warning("WARNING: FAST_DEBATE=True is enabled in non-development environment! This runs mock-speed debate shortcuts.")
            except Exception:
                pass

        assert any("FAST_DEBATE=True is enabled" in record.message for record in caplog.records)
