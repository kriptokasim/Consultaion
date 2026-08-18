from typing import Any, cast

from database import get_session as base_get_session
from fastapi import HTTPException, Request, status
from sqlmodel import Session
from sse_backend import BaseSSEBackend


def get_session() -> Session:
    yield from base_get_session()


class _RequestSSEBackendProxy:
    """Request-scoped SSE proxy that removes redundant channel pre-creation.

    Debate creation historically called ``create_channel()`` after committing the
    debate/quota transaction. RedisChannelBackend.create_channel() only writes an
    otherwise-unused ``sse:meta:*`` key, so a Redis failure in that narrow
    post-commit window could turn a successfully committed run into an HTTP 500.

    The dependency already performs a readiness ping before the endpoint body.
    Request-time ``create_channel()`` is therefore intentionally a no-op. All
    real transport operations are delegated to the application backend. Memory
    subscriptions remain correct because the bound backend ``subscribe()``
    method creates its own in-memory channel; Redis publish/subscribe does not
    require the metadata key. Worker/global backend access is unaffected because
    only FastAPI dependency consumers receive this proxy.
    """

    def __init__(self, backend: BaseSSEBackend) -> None:
        self._backend = backend

    async def create_channel(self, channel_id: str) -> None:
        # Deliberately no network I/O in the request commit boundary.
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)


async def get_sse_backend(request: Request) -> BaseSSEBackend:
    """Return a readiness-checked request SSE backend.

    FastAPI resolves this dependency before entering endpoint bodies. A failed
    Redis/SSE health probe therefore prevents quota reservation or debate
    mutation. The returned request proxy also suppresses the redundant
    post-commit ``create_channel`` write, closing the remaining ping→commit→SET
    TOCTOU failure boundary while delegating actual publish/subscribe work to the
    canonical application backend.
    """
    backend: BaseSSEBackend = request.app.state.sse_backend
    try:
        healthy = await backend.ping()
    except Exception:
        healthy = False

    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "sse_backend_unavailable",
                "message": "Realtime transport is temporarily unavailable. Please retry shortly.",
            },
            headers={"Retry-After": "5"},
        )

    return cast(BaseSSEBackend, _RequestSSEBackendProxy(backend))
