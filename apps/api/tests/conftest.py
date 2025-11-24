import pytest
import os

# Simplify ASGI middleware for test stability
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

from worker.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


@pytest.fixture(scope="session", params=["asyncio"])
def anyio_backend(request):
    """Limit anyio tests to asyncio backend since trio isn't available in CI."""
    return request.param
