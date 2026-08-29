"""Execution-runtime guards for debate SSE and checkpoint ownership.

These guards close two cross-cutting ownership gaps without duplicating checks
inside every engine:

1. Durable debate SSE events are fenced immediately before publication so a
   worker that loses ownership between DB commit and transport publish cannot
   leak stale lifecycle/final events.
2. Multi-instance SSE concurrency leases fail closed when Redis is the expected
   authority but becomes unavailable. Process-local memory is not a valid
   substitute for a global production concurrency limit unless fail-open is
   explicitly enabled.
3. Staging follows the same fail-closed checkpoint lease rules as production.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from database_async import async_session_scope
from models import Debate
from orchestration.execution_context import get_current_execution_lease
from orchestration.execution_lease import ExecutionSupersededError

logger = logging.getLogger(__name__)

# DB-checking every token fragment would put provider streaming behind a DB RTT.
# These events are loss-tolerant and are already cancelled by the orchestration
# lease-lost race. Every other debate event gets a fresh ownership check.
_HIGH_FREQUENCY_EVENTS = frozenset({
    "model_response_delta",
    "arena_synthesis_delta",
    "agent_progress_delta",
    "heartbeat",
})


async def _assert_live_publish_ownership(lease) -> None:
    now = datetime.now(timezone.utc)
    stmt = (
        sa.select(Debate.id)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .where(Debate.lease_expires_at.is_not(None))
        .where(Debate.lease_expires_at > now)
    )
    async with async_session_scope() as session:
        result = await session.execute(stmt)
        if result.first() is not None:
            return

    lease.lease_lost_event.set()
    logger.warning(
        "sse.execution_publish_rejected debate_id=%s owner=%s epoch=%s",
        lease.debate_id,
        lease.owner_id,
        lease.lease_epoch,
    )
    raise ExecutionSupersededError(
        f"Debate {lease.debate_id}: SSE publication rejected because execution "
        f"lease {lease.lease_epoch} is no longer owned by {lease.owner_id}."
    )


class ExecutionFencedSSEBackend:
    """Transparent backend decorator enforcing the execution publish fence."""

    def __init__(self, backend) -> None:
        self._backend = backend

    async def publish(self, channel_id: str, event: dict) -> None:
        lease = get_current_execution_lease()
        if lease is not None and channel_id == f"debate:{lease.debate_id}":
            if lease.lease_lost_event.is_set():
                raise ExecutionSupersededError(
                    f"Debate {lease.debate_id}: stale execution attempted SSE publication."
                )
            event_type = str(event.get("type") or "")
            if event_type not in _HIGH_FREQUENCY_EVENTS:
                await _assert_live_publish_ownership(lease)
        await self._backend.publish(channel_id, event)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)


_installed = False
_original_provider_get = None
_original_stream_try_acquire = None
_original_checkpoint_resolve = None


def _distributed_sse_leases_required() -> bool:
    """Return True when process-local lease fallback would violate deployment semantics."""
    from config import settings

    if getattr(settings, "IS_LOCAL_ENV", False):
        return False
    return bool(
        getattr(settings, "REDIS_URL", None)
        or getattr(settings, "SSE_REDIS_URL", None)
        or str(getattr(settings, "SSE_BACKEND", "")).lower() == "redis"
    )


async def _strict_stream_try_acquire(self, debate_id: str, subscriber_id: str, user_id: str | None = None):
    """Use Redis as the authority when distributed leases are required.

    The legacy implementation silently fell through to a process-local memory
    limiter when the Redis lease script returned a backend error. In a
    multi-instance deployment each process then enforced its own independent
    limit, effectively multiplying the advertised concurrency cap.
    """
    from config import settings
    from metrics import increment_metric
    from redis_pool import get_async_redis_client
    from services.lease import sse_acquire_lease_async
    from sse_backend import StreamLeaseResult

    if not _distributed_sse_leases_required():
        return await _original_stream_try_acquire(self, debate_id, subscriber_id, user_id)

    # An explicitly configured fail-open policy may use the legacy memory
    # fallback. It remains an opt-in operational trade-off, never the default.
    fail_open = bool(getattr(settings, "SSE_LEASE_FAIL_OPEN", False))
    identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
    client = get_async_redis_client()
    if client is None:
        increment_metric("sse.lease.backend_unavailable")
        if fail_open:
            return await _original_stream_try_acquire(self, debate_id, subscriber_id, user_id)
        return StreamLeaseResult.ERROR_FAIL_CLOSED

    try:
        result = await sse_acquire_lease_async(
            client,
            self._lease_key(debate_id),
            identity,
            self._max_streams,
            self._lease_ttl,
        )
    except Exception as exc:
        logger.warning("Distributed SSE lease acquire raised unexpectedly: %s", exc)
        result = -1

    if result in (1, 2):
        increment_metric("sse.lease.acquired")
        return StreamLeaseResult.ACQUIRED
    if result == 0:
        increment_metric("sse.lease.denied")
        return StreamLeaseResult.DENIED

    increment_metric("sse.lease.backend_unavailable")
    if fail_open:
        return await _original_stream_try_acquire(self, debate_id, subscriber_id, user_id)
    return StreamLeaseResult.ERROR_FAIL_CLOSED


def _strict_checkpoint_resolve(execution_lease, allow_unfenced: bool = False):
    """Make staging obey the same checkpoint fencing contract as production."""
    from config import settings
    from orchestration.execution_context import get_current_execution_lease

    lease = execution_lease or get_current_execution_lease()
    env = str(getattr(settings, "APP_ENV", "local")).lower()
    if lease is None and env in {"production", "staging"}:
        if allow_unfenced:
            return None
        raise RuntimeError(
            "run_with_checkpoint requires an ExecutionLease in production/staging "
            "(pass execution_lease= or bind one via execution_context)."
        )
    return _original_checkpoint_resolve(execution_lease, allow_unfenced=allow_unfenced)


def install_sse_execution_guard() -> None:
    """Install the cross-cutting runtime guards exactly once."""
    global _installed, _original_provider_get, _original_stream_try_acquire, _original_checkpoint_resolve
    if _installed:
        return

    from orchestration import checkpoints
    from sse_backend import SSEBackendProvider, StreamLeaseManager

    _original_provider_get = SSEBackendProvider.get
    _original_stream_try_acquire = StreamLeaseManager.try_acquire
    _original_checkpoint_resolve = checkpoints._resolve_lease

    def guarded_get(provider):
        backend = _original_provider_get(provider)
        if isinstance(backend, ExecutionFencedSSEBackend):
            return backend
        wrapped = ExecutionFencedSSEBackend(backend)
        provider._backend = wrapped
        return wrapped

    SSEBackendProvider.get = guarded_get  # type: ignore[method-assign]
    StreamLeaseManager.try_acquire = _strict_stream_try_acquire  # type: ignore[method-assign]
    checkpoints._resolve_lease = _strict_checkpoint_resolve
    _installed = True
