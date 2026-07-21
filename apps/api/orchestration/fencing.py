"""PS156 Track F — Fenced debate writes.

Every critical Debate mutation (status transitions, final_content/final_meta,
attempt completion, billing finalization, continuation completion) must be
conditional on the full fencing identity::

    Debate.id == lease.debate_id
    Debate.runner_id == lease.owner_id
    Debate.lease_epoch == lease.lease_epoch

A zero-row update means ownership moved on: raise
:class:`ExecutionSupersededError` and stop writing related state instead of
clobbering the newer owner's work.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from models import Debate

from orchestration.execution_context import ExecutionLease
from orchestration.execution_lease import ExecutionSupersededError

logger = logging.getLogger(__name__)


def fenced_debate_stmt(lease: ExecutionLease):
    """Base UPDATE constrained to a live lease's fencing identity."""
    now = datetime.now(timezone.utc)
    return (
        sa.update(Debate)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .where(Debate.status == "running")
        .where(Debate.lease_expires_at.is_not(None))
        .where(Debate.lease_expires_at > now)
    )


async def fenced_debate_update(
    session,
    lease: ExecutionLease,
    values: dict[str, Any],
    *,
    extra_where: Optional[list] = None,
    what: str = "write",
) -> None:
    """Apply *values* to the Debate iff this worker still owns the lease.

    Raises ExecutionSupersededError when zero rows match.
    """
    stmt = fenced_debate_stmt(lease).values(**values)
    if extra_where:
        for cond in extra_where:
            stmt = stmt.where(cond)
    result = await session.execute(stmt)
    if result.rowcount == 0:
        logger.warning(
            "debate.fenced_write_rejected debate_id=%s owner=%s epoch=%s what=%s",
            lease.debate_id, lease.owner_id, lease.lease_epoch, what,
        )
        lease.lease_lost_event.set()
        raise ExecutionSupersededError(
            f"Debate {lease.debate_id}: fenced {what} rejected — lease "
            f"{lease.lease_epoch} no longer owned by {lease.owner_id}."
        )


async def assert_execution_ownership(session, lease: ExecutionLease) -> None:
    """Read-side ownership check (SELECT) for flows about to write state."""
    now = datetime.now(timezone.utc)
    stmt = (
        sa.select(Debate.id)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .where(Debate.status == "running")
        .where(Debate.lease_expires_at.is_not(None))
        .where(Debate.lease_expires_at > now)
        .with_for_update()
    )
    result = await session.execute(stmt)
    if result.first() is None:
        lease.lease_lost_event.set()
        raise ExecutionSupersededError(
            f"Debate {lease.debate_id}: execution ownership verification failed "
            f"for {lease.owner_id} at epoch {lease.lease_epoch}."
        )
