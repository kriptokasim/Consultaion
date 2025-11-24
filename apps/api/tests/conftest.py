import pytest
import os

# Simplify ASGI middleware for test stability
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

# Default test environment settings
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")  # Default to SQLite for tests
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("DISABLE_AUTORUN", "1")
os.environ.setdefault("DISABLE_RATINGS", "1")
os.environ.setdefault("FAST_DEBATE", "1")
os.environ.setdefault("SSE_BACKEND", "memory")
os.environ.setdefault("RL_MAX_CALLS", "1000")
os.environ.setdefault("AUTH_RL_MAX_CALLS", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_MAX_RUNS_PER_HOUR", "50")
os.environ.setdefault("DEFAULT_MAX_TOKENS_PER_DAY", "150000")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ.setdefault("ENV", "test")


from worker.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


@pytest.fixture(scope="session", params=["asyncio"])
def anyio_backend(request):
    """Limit anyio tests to asyncio backend since trio isn't available in CI."""
    return request.param


@pytest.fixture(autouse=True)
def reset_global_state(request):
    """
    Runs before every test:
    - Reloads AppSettings from the current environment (unless test has custom DB).
    - Clears provider health registry.
    """
    from config import settings
    from tests.utils import reset_provider_health

    # Skip settings reload if test module has set up its own DATABASE_URL
    # (e.g., test_app.py, test_ratings.py, test_parliament_failure_tolerance.py)
    skip_reload = hasattr(request.module, 'test_db_path')
    
    if not skip_reload:
        # Reload settings from env to ensure clean state
        settings.reload()

    # Reset provider health (circuit breaker state)
    reset_provider_health()

    yield

