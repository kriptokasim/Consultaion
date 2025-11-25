import os
import pytest
from pydantic import ValidationError as PydanticValidationError
from config import AppSettings

def test_config_local_env_defaults():
    # ENV=local -> COOKIE_SECURE=False, ENABLE_SEC_HEADERS=False
    os.environ["ENV"] = "local"
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["DATABASE_URL"] = "sqlite:///test.db"
    
    settings = AppSettings()
    assert settings.IS_LOCAL_ENV is True
    assert settings.COOKIE_SECURE is False
    assert settings.ENABLE_SEC_HEADERS is False

def test_config_prod_env_defaults():
    # ENV=production -> COOKIE_SECURE=True, ENABLE_SEC_HEADERS=True
    os.environ["ENV"] = "production"
    os.environ["JWT_SECRET"] = "prod-secret-must-be-long-enough-32chars"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # Required for prod
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
    
    settings = AppSettings()
    assert settings.IS_LOCAL_ENV is False
    assert settings.COOKIE_SECURE is True
    assert settings.ENABLE_SEC_HEADERS is True

def test_config_workers_validation_memory_backend():
    # WORKERS > 1 with SSE_BACKEND=memory should fail
    os.environ["ENV"] = "production"
    os.environ["JWT_SECRET"] = "prod-secret-must-be-long-enough-32chars"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
    os.environ["WEB_CONCURRENCY"] = "2"
    os.environ["SSE_BACKEND"] = "memory"
    
    with pytest.raises(PydanticValidationError) as exc:
        AppSettings()
    assert "SSE_BACKEND='redis' is required when running with 2 workers" in str(exc.value)

def test_config_workers_validation_redis_backend():
    # WORKERS > 1 with SSE_BACKEND=redis should pass
    os.environ["ENV"] = "production"
    os.environ["JWT_SECRET"] = "prod-secret-must-be-long-enough-32chars"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
    os.environ["WEB_CONCURRENCY"] = "2"
    os.environ["SSE_BACKEND"] = "redis"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
    
    settings = AppSettings()
    assert settings.WEB_CONCURRENCY == 2
    assert settings.SSE_BACKEND == "redis"
