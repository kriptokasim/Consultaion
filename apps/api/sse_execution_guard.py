"""Execution-lease fence for debate SSE publications.

The engines persist durable state under a database lease fence, then publish
SSE. Without a second ownership check at that boundary, a takeover can occur
between commit and publish and the stale worker can emit a valid-looking event
for work it no longer owns.

This decorator centralizes the rule for every engine that publishes through the
canonical SSE backend. High-frequency token deltas use the in-memory
``lease_lost_event`` fast path; durable/lifecycle events additionally verify the
owner+epoch+expiry in the database immediately before transport publication.
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


def install_sse_execution_guard() -> None:
    """Wrap the canonical SSE provider once, before its first runtime use."""
    global _installed, _original_provider_get
    if _installed:
        return

    from sse_backend import SSEBackendProvider

    _original_provider_get = SSEBackendProvider.get

    def guarded_get(provider):
        backend = _original_provider_get(provider)
        if isinstance(backend, ExecutionFencedSSEBackend):
            return backend
        wrapped = ExecutionFencedSSEBackend(backend)
        provider._backend = wrapped
        return wrapped

    SSEBackendProvider.get = guarded_get  # type: ignore[method-assign]
    _installed = True
