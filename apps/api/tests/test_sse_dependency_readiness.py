from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from deps import get_sse_backend


class _Backend:
    def __init__(self, *, healthy: bool = True, raises: bool = False):
        self.healthy = healthy
        self.raises = raises
        self.ping_calls = 0
        self.create_channel_calls = 0
        self.publish_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        if self.raises:
            raise RuntimeError("redis unavailable")
        return self.healthy

    async def create_channel(self, channel_id: str) -> None:
        self.create_channel_calls += 1

    async def publish(self, channel_id: str, event: dict) -> None:
        self.publish_calls += 1


@pytest.mark.anyio
async def test_sse_dependency_returns_readiness_checked_proxy():
    backend = _Backend(healthy=True)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sse_backend=backend)))

    resolved = await get_sse_backend(request)

    assert resolved is not backend
    assert backend.ping_calls == 1

    # Request-path channel pre-creation is deliberately suppressed so a
    # post-commit Redis SET cannot turn a committed debate into an HTTP error.
    await resolved.create_channel("debate:test")
    assert backend.create_channel_calls == 0

    # Real transport operations still delegate to the canonical backend.
    await resolved.publish("debate:test", {"type": "notice"})
    assert backend.publish_calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize("backend", [_Backend(healthy=False), _Backend(raises=True)])
async def test_sse_dependency_rejects_unready_backend_before_endpoint_body(backend):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sse_backend=backend)))

    with pytest.raises(HTTPException) as exc:
        await get_sse_backend(request)

    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "sse_backend_unavailable"
    assert exc.value.headers == {"Retry-After": "5"}
    assert backend.create_channel_calls == 0
