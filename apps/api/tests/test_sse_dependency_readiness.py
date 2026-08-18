from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from deps import get_sse_backend


class _Backend:
    def __init__(self, *, healthy: bool = True, raises: bool = False):
        self.healthy = healthy
        self.raises = raises
        self.ping_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        if self.raises:
            raise RuntimeError("redis unavailable")
        return self.healthy


@pytest.mark.anyio
async def test_sse_dependency_returns_healthy_backend():
    backend = _Backend(healthy=True)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sse_backend=backend)))

    resolved = await get_sse_backend(request)

    assert resolved is backend
    assert backend.ping_calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize("backend", [_Backend(healthy=False), _Backend(raises=True)])
async def test_sse_dependency_rejects_unready_backend_before_endpoint_body(backend):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sse_backend=backend)))

    with pytest.raises(HTTPException) as exc:
        await get_sse_backend(request)

    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "sse_backend_unavailable"
    assert exc.value.headers == {"Retry-After": "5"}
