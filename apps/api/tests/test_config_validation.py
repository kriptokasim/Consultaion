import pytest
from config import AppSettings
from pydantic import ValidationError as PydanticValidationError


def test_config_local_env_defaults(monkeypatch):
    # ENV=local -> COOKIE_SECURE=False, ENABLE_SEC_HEADERS=False
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    
    settings = AppSettings()
    assert settings.IS_LOCAL_ENV is True
    assert settings.COOKIE_SECURE is False
    assert settings.ENABLE_SEC_HEADERS is False

def test_config_prod_env_defaults(monkeypatch):
    # ENV=production -> COOKIE_SECURE=True, ENABLE_SEC_HEADERS=True
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-must-be-long-enough-32chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")  # Required for prod
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    
    settings = AppSettings()
    assert settings.IS_LOCAL_ENV is False
    assert settings.COOKIE_SECURE is True
    assert settings.ENABLE_SEC_HEADERS is True

def test_config_workers_validation_memory_backend(monkeypatch):
    # WORKERS > 1 with SSE_BACKEND=memory should fail
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-must-be-long-enough-32chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    monkeypatch.setenv("SSE_BACKEND", "memory")
    
    with pytest.raises(PydanticValidationError) as exc:
        AppSettings()
    assert "SSE_BACKEND='redis' is required when running with 2 workers" in str(exc.value)

def test_config_workers_validation_redis_backend(monkeypatch):
    # WORKERS > 1 with SSE_BACKEND=redis should pass
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-secret-must-be-long-enough-32chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    monkeypatch.setenv("SSE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    
    settings = AppSettings()
    assert settings.WEB_CONCURRENCY == 2
    assert settings.SSE_BACKEND == "redis"
