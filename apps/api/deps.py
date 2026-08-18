from database import get_session as base_get_session
from fastapi import HTTPException, Request, status
from sqlmodel import Session
from sse_backend import BaseSSEBackend


def get_session() -> Session:
    yield from base_get_session()


async def get_sse_backend(request: Request) -> BaseSSEBackend:
    """Return an SSE backend only when it is ready for request-time use.

    Debate creation reserves hourly/monthly usage and may reserve hosted credits
    before creating its SSE channel. If the Redis-backed SSE transport is down,
    allowing the endpoint body to start can leave a committed queued debate and
    consumed usage even though channel setup later fails.

    FastAPI resolves this dependency before entering the endpoint body. Treat a
    failed backend health probe as a 503 readiness failure so no business
    mutation or quota reservation starts. MemoryChannelBackend.ping() is always
    healthy; RedisChannelBackend.ping() performs the actual backend probe.
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

    return backend
