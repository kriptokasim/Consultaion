"""PS156 Tracks C+D — Atomic execution-lease operations.

All lease mutations are single atomic UPDATE statements evaluated by the
database; there is no read-then-write anywhere in the lease lifecycle.

- Acquisition requires the lease to be free (no runner, no expiry, or expired)
  and the Debate to be in a non-terminal status. Every acquisition increments
  ``lease_epoch`` (fencing token) and ``run_attempt`` exactly once.
- Heartbeat renewal is conditional on (debate_id, owner_id, lease_epoch,
  status='running') and never increments either counter. ``rowcount == 0``
  means ownership was lost — it is never treated as success.
- Release is conditional on the same identity triple, so a stale worker can
  never clear a newer owner's lease.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from database_async import async_session_scope
from metrics import increment_metric
from models import Debate

from orchestration.execution_context import ExecutionLease, new_owner_id

logger = logging.getLogger(__name__)

#: Statuses that must never receive a new normal execution lease (Track C3).
TERMINAL_STATUSES = ("completed", "completed_with_warnings", "cancelled")


class LeaseRenewResult(Enum):
    RENEWED = "renewed"
    OWNERSHIP_LOST = "ownership_lost"


class ExecutionSupersededError(Exception):
    """A newer execution owner took over; this worker must stop immediately.

    Carries no retry semantics — the newer owner is responsible for the Run.
    """


class LeaseInfrastructureError(Exception):
    """Heartbeat/lease storage became unreliable; abort without touching state."""


class LeaseAcquireResult:
    def __init__(self, lease: Optional[ExecutionLease], conflict: bool = False):
        self.lease = lease
        self.conflict = conflict

    @property
    def acquired(self) -> bool:
        return self.lease is not None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def acquire_execution_lease(
    debate_id: str,
    *,
    owner_id: Optional[str] = None,
    lease_seconds: int,
) -> LeaseAcquireResult:
    """Atomically acquire the execution lease for *debate_id*.

    One UPDATE ... RETURNING; exactly one concurrent caller wins. Returns a
    bound :class:`ExecutionLease` on success, or ``conflict=True`` when the
    lease is held by a live owner or the debate is terminal.
    """
    owner = owner_id or new_owner_id()
    now = _now()
    expires = now + timedelta(seconds=lease_seconds)

    stmt = (
        sa.update(Debate)
        .where(Debate.id == debate_id)
        .where(~Debate.status.in_(TERMINAL_STATUSES))
        .where(
            sa.or_(
                Debate.runner_id.is_(None),
                Debate.lease_expires_at.is_(None),
                Debate.lease_expires_at < now,
            )
        )
        .values(
            runner_id=owner,
            execution_owner_id=owner,
            lease_epoch=Debate.lease_epoch + 1,
            lease_expires_at=expires,
            last_heartbeat_at=now,
            execution_started_at=now,
            status="running",
            run_attempt=Debate.run_attempt + 1,
        )
        .returning(Debate.lease_epoch, Debate.run_attempt)
    )

    async with async_session_scope() as session:
        result = await session.execute(stmt)
        row = result.first()
        await session.commit()

    if row is None:
        increment_metric("debate.lease.acquire_conflict")
        logger.info(
            "debate.lease.acquire_conflict debate_id=%s owner=%s",
            debate_id, owner,
        )
        return LeaseAcquireResult(None, conflict=True)

    lease = ExecutionLease.create(
        debate_id, owner_id=owner, lease_epoch=row[0], run_attempt=row[1]
    )
    increment_metric("debate.lease.acquired")
    logger.info(
        "debate.lease.acquired debate_id=%s owner=%s epoch=%s attempt=%s",
        debate_id, owner, lease.lease_epoch, lease.run_attempt,
    )
    return LeaseAcquireResult(lease)


async def renew_execution_lease(
    lease: ExecutionLease,
    *,
    lease_seconds: int,
) -> LeaseRenewResult:
    """Conditionally extend the lease. Zero rows updated ⇒ ownership lost."""
    now = _now()
    stmt = (
        sa.update(Debate)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .where(Debate.status == "running")
        .values(
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            last_heartbeat_at=now,
        )
    )
    async with async_session_scope() as session:
        result = await session.execute(stmt)
        await session.commit()

    if result.rowcount == 1:
        increment_metric("debate.lease.heartbeat_success")
        return LeaseRenewResult.RENEWED

    increment_metric("debate.lease.ownership_lost")
    logger.warning(
        "debate.lease.ownership_lost debate_id=%s owner=%s epoch=%s",
        lease.debate_id, lease.owner_id, lease.lease_epoch,
    )
    return LeaseRenewResult.OWNERSHIP_LOST


async def release_execution_lease(lease: ExecutionLease) -> bool:
    """Conditionally clear the lease. Never clears a newer owner's lease."""
    stmt = (
        sa.update(Debate)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .values(runner_id=None, lease_expires_at=None, execution_owner_id=None)
    )
    async with async_session_scope() as session:
        result = await session.execute(stmt)
        await session.commit()

    if result.rowcount == 1:
        increment_metric("debate.lease.release_success")
        return True
    increment_metric("debate.lease.release_mismatch")
    logger.info(
        "debate.lease.release_mismatch debate_id=%s owner=%s epoch=%s",
        lease.debate_id, lease.owner_id, lease.lease_epoch,
    )
    return False


async def heartbeat_loop(
    lease: ExecutionLease,
    *,
    lease_seconds: int,
    interval_seconds: int,
    failure_threshold: int,
    stop_event,
) -> None:
    """Renew the lease until stopped; set ``lease.lease_lost_event`` on loss.

    - A definite rowcount-zero mismatch aborts immediately.
    - Consecutive transport/infrastructure failures abort once the configured
      threshold is reached (before the lease would expire).
    """
    from metrics import increment_metric as _inc

    consecutive_failures = 0
    while not stop_event.is_set():
        try:
            await asyncio_wait(stop_event, interval_seconds)
        except asyncio.CancelledError:
            raise
        if stop_event.is_set():
            return
        try:
            result = await renew_execution_lease(lease, lease_seconds=lease_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # infrastructure failure — retry until threshold
            consecutive_failures += 1
            _inc("debate.lease.heartbeat_failure")
            logger.warning(
                "debate.lease.heartbeat_failure debate_id=%s owner=%s epoch=%s "
                "failures=%s error=%s",
                lease.debate_id, lease.owner_id, lease.lease_epoch,
                consecutive_failures, exc,
            )
            if consecutive_failures >= failure_threshold:
                logger.error(
                    "debate.lease.infrastructure_abort debate_id=%s owner=%s epoch=%s",
                    lease.debate_id, lease.owner_id, lease.lease_epoch,
                )
                lease.lease_lost_event.set()
                return
            continue

        consecutive_failures = 0
        if result is LeaseRenewResult.OWNERSHIP_LOST:
            lease.lease_lost_event.set()
            return


async def asyncio_wait(event, timeout: float) -> None:
    """Sleep up to *timeout*, returning early when *event* is set."""
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
