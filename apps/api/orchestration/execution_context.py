"""PS156 Track B — Execution ownership context.

An :class:`ExecutionLease` identifies exactly one orchestration invocation.
It is propagated through the async call graph via a :class:`ContextVar`, so
child tasks spawned by the orchestration body inherit the same fencing
identity without explicit parameter threading.

Rules enforced here:

- ``owner_id`` is unique per invocation (hostname + pid + UUID4 — the UUID
  fragment is mandatory so two invocations in the same worker process never
  share an owner identity);
- production checkpoint/state writes must fail closed when no execution
  context is bound (tests may bind a fake context explicitly);
- never log prompt contents or provider credentials with this context.
"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def new_owner_id() -> str:
    """Return a globally unique execution-owner ID for one invocation.

    Format: ``<hostname>:<pid>:<uuid4>``. The UUID4 fragment guarantees
    uniqueness even for two invocations within the same worker process.
    """
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"


@dataclass(frozen=True)
class ExecutionLease:
    """Immutable fencing identity for one Debate execution."""

    debate_id: str
    owner_id: str
    lease_epoch: int
    run_attempt: int
    acquired_at: datetime
    # Set when heartbeat renewal or a fenced write detects ownership loss;
    # the orchestration body races against this event (Track E).
    lease_lost_event: asyncio.Event = field(default_factory=asyncio.Event, compare=False)

    @classmethod
    def create(
        cls,
        debate_id: str,
        *,
        owner_id: Optional[str] = None,
        lease_epoch: int,
        run_attempt: int,
    ) -> "ExecutionLease":
        return cls(
            debate_id=debate_id,
            owner_id=owner_id or new_owner_id(),
            lease_epoch=lease_epoch,
            run_attempt=run_attempt,
            acquired_at=datetime.now(timezone.utc),
        )


current_execution_lease: ContextVar[Optional[ExecutionLease]] = ContextVar(
    "current_execution_lease", default=None
)


def get_current_execution_lease() -> Optional[ExecutionLease]:
    """Return the bound lease for this task context, if any."""
    return current_execution_lease.get()


def require_current_execution_lease() -> ExecutionLease:
    """Fail-closed accessor: raise when no execution context is bound."""
    lease = current_execution_lease.get()
    if lease is None:
        raise RuntimeError(
            "No execution lease bound to this context. Orchestrated writes "
            "require an active ExecutionLease (bind_execution_lease)."
        )
    return lease


def bind_execution_lease(lease: ExecutionLease) -> Token:
    """Bind *lease* to the current task context; returns the reset token."""
    return current_execution_lease.set(lease)


def reset_execution_lease(token: Token) -> None:
    """Restore the previous context state."""
    current_execution_lease.reset(token)
