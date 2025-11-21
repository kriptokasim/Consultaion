import pytest


@pytest.fixture(scope="session", params=["asyncio"])
def anyio_backend(request):
    """Limit anyio tests to asyncio backend since trio isn't available in CI."""
    return request.param
