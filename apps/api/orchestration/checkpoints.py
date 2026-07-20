"""PS156 Tracks G/H/I — Atomic, owner-fenced stage checkpoints.

Every checkpoint mutation is a compare-and-set UPDATE conditioned on the full
ownership identity (checkpoint id + status + owner_id + lease_epoch + attempt
[+ input_hash]). No stage can be executed twice concurrently, and a stale
worker can never overwrite a newer owner's checkpoint state.

Staleness/takeover policy (H): a ``running`` checkpoint may only be taken over
when it is objectively stale (no heartbeat/update within
CHECKPOINT_STALE_SECONDS) **and** the current worker holds the Debate
execution lease — which proves the previous owner's Debate lease is gone.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import sqlalchemy as sa
from config import settings
from database_async import async_session_scope
from models import Debate, DebateStageCheckpoint
from sqlmodel import select

from orchestration.execution_context import (
    ExecutionLease,
    get_current_execution_lease,
)
from orchestration.execution_lease import ExecutionSupersededError
from orchestration.stage_graph import StageKey

logger = logging.getLogger(__name__)

# Claimable base states (Track G3). "running" is claimable only via the
# stale-takeover path.
_CLAIMABLE_STATUSES = ("pending", "failed", "invalidated")


class CheckpointOwnershipLostError(RuntimeError):
    """This worker lost ownership of the checkpoint mid-execution."""


class CheckpointIntegrityError(RuntimeError):
    """Checkpoint state violated expectations (e.g. row deleted mid-run)."""


class LeaseOwnershipLost(ExecutionSupersededError):  # backward-compat alias
    """Raised when a worker no longer owns the debate execution lease."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_debate_lease_exists(lease: ExecutionLease, *, now: Optional[datetime] = None):
    """SQL predicate proving that *lease* is still live at statement time."""
    checked_at = now or _now()
    return sa.exists(
        sa.select(Debate.id)
        .where(Debate.id == lease.debate_id)
        .where(Debate.runner_id == lease.owner_id)
        .where(Debate.lease_epoch == lease.lease_epoch)
        .where(Debate.status == "running")
        .where(Debate.lease_expires_at.is_not(None))
        .where(Debate.lease_expires_at > checked_at)
    )


def _checkpoint_is_stale(cp: DebateStageCheckpoint, *, now: datetime) -> bool:
    """Return whether a running checkpoint has exceeded the stale window."""
    activity_at = cp.heartbeat_at or cp.updated_at or cp.started_at
    if activity_at is None:
        return True
    if activity_at.tzinfo is None:
        activity_at = activity_at.replace(tzinfo=timezone.utc)
    return activity_at < now - timedelta(seconds=settings.CHECKPOINT_STALE_SECONDS)


async def _assert_debate_lease(session, lease: ExecutionLease) -> None:
    """Verify the Debate-level lease is still ours (fails closed)."""
    now = _now()
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
            f"Debate {lease.debate_id}: lease no longer owned by "
            f"{lease.owner_id} at epoch {lease.lease_epoch}."
        )


async def _assert_lease_owner(
    session,
    debate_id: str,
    owner_id: Optional[str],
    lease_epoch: Optional[int],
) -> None:
    """PS155-compatible lease assertion (legacy callers and tests).

    Locks and verifies the debate lease for the surrounding transaction.
    Both None → unfenced legacy mode (no-op); partial identity → ValueError.
    """
    if owner_id is None and lease_epoch is None:
        return
    if not owner_id or lease_epoch is None:
        raise ValueError("owner_id and lease_epoch must be provided together")

    stmt = (
        select(Debate)
        .where(Debate.id == debate_id)
        .where(Debate.execution_owner_id == owner_id)
        .where(Debate.lease_epoch == lease_epoch)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    if result.scalars().first() is None:
        raise LeaseOwnershipLost(
            f"Debate {debate_id}: execution lease is no longer owned by "
            f"{owner_id} at epoch {lease_epoch}."
        )


def _resolve_lease(execution_lease: Optional[ExecutionLease]) -> Optional[ExecutionLease]:
    """Resolve the execution lease for a checkpointed stage.

    Track G1: production execution fails closed when no lease context exists;
    local/test execution may run unfenced (legacy behavior) so unit tests and
    offline tooling can exercise stages without a full lease lifecycle.
    """
    lease = execution_lease or get_current_execution_lease()
    if lease is None and getattr(settings, "APP_ENV", "local") == "production":
        raise RuntimeError(
            "run_with_checkpoint requires an ExecutionLease (pass "
            "execution_lease= or bind one via execution_context)."
        )
    return lease


async def _get_checkpoint(session, debate_id: str, stage_key: str) -> Optional[DebateStageCheckpoint]:
    stmt = (
        select(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == debate_id)
        .where(DebateStageCheckpoint.stage_key == stage_key)
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def _cas_claim(session, lease: ExecutionLease, stage_key: str, input_hash: str) -> Optional[int]:
    """Atomically claim an existing checkpoint. Returns new attempt or None."""
    now = _now()
    stale_before = now - timedelta(seconds=settings.CHECKPOINT_STALE_SECONDS)

    # Base claim: checkpoint is in a claimable state, or completed output was
    # produced for different input and must be recomputed.
    base = (
        sa.update(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == lease.debate_id)
        .where(DebateStageCheckpoint.stage_key == stage_key)
        .where(
            sa.or_(
                DebateStageCheckpoint.status.in_(_CLAIMABLE_STATUSES),
                sa.and_(
                    DebateStageCheckpoint.status == "completed",
                    DebateStageCheckpoint.input_hash != input_hash,
                ),
            )
        )
        .where(_active_debate_lease_exists(lease, now=now))
    )
    values = dict(
        status="running",
        owner_id=lease.owner_id,
        lease_epoch=lease.lease_epoch,
        attempt=DebateStageCheckpoint.attempt + 1,
        input_hash=input_hash,
        started_at=now,
        updated_at=now,
        heartbeat_at=now,
        error_message=None,
        error_code=None,
        failed_at=None,
        completed_at=None,
        output_reference=None,
    )
    result = await session.execute(base.values(**values))
    if result.rowcount == 1:
        cp = await _get_checkpoint(session, lease.debate_id, stage_key)
        return cp.attempt if cp else None

    # Stale takeover: running, objectively stale, owned by someone else.
    # Holding the Debate lease (verified by caller) proves the old owner's
    # Debate lease is gone, so its checkpoint cannot still be live (H1/H2).
    takeover = (
        sa.update(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == lease.debate_id)
        .where(DebateStageCheckpoint.stage_key == stage_key)
        .where(DebateStageCheckpoint.status == "running")
        .where(DebateStageCheckpoint.owner_id != lease.owner_id)
        .where(_active_debate_lease_exists(lease, now=now))
        .where(
            sa.or_(
                DebateStageCheckpoint.heartbeat_at < stale_before,
                sa.and_(
                    DebateStageCheckpoint.heartbeat_at.is_(None),
                    DebateStageCheckpoint.updated_at < stale_before,
                ),
                sa.and_(
                    DebateStageCheckpoint.heartbeat_at.is_(None),
                    DebateStageCheckpoint.updated_at.is_(None),
                    DebateStageCheckpoint.started_at < stale_before,
                ),
            )
        )
    )
    result = await session.execute(takeover.values(**values))
    if result.rowcount == 1:
        logger.warning(
            "checkpoint.stale_takeover debate_id=%s stage=%s owner=%s epoch=%s",
            lease.debate_id, stage_key, lease.owner_id, lease.lease_epoch,
        )
        cp = await _get_checkpoint(session, lease.debate_id, stage_key)
        return cp.attempt if cp else None
    return None


async def _insert_new_checkpoint(session, lease: ExecutionLease, stage_key: str, input_hash: str) -> Optional[int]:
    """Insert a fresh owned/running checkpoint; None when a race lost."""
    now = _now()
    cp = DebateStageCheckpoint(
        debate_id=lease.debate_id,
        stage_key=stage_key,
        status="running",
        input_hash=input_hash,
        started_at=now,
        updated_at=now,
        heartbeat_at=now,
        attempt=1,
        owner_id=lease.owner_id,
        lease_epoch=lease.lease_epoch,
    )
    session.add(cp)
    try:
        await session.flush()
    except sa.exc.IntegrityError:
        await session.rollback()
        return None  # concurrent insert — caller re-reads and waits/claims
    return 1


async def _wait_for_checkpoint(session_factory, lease: ExecutionLease, stage_key: str, input_hash: str) -> str:
    """Poll until the checkpoint becomes completed/failed/claimable/timeout.

    Returns the terminal action to take: "load", "claim", or raises.
    Bounded exponential backoff with jitter (Track H).
    """
    delay = settings.CHECKPOINT_POLL_INITIAL_MS / 1000.0
    max_delay = settings.CHECKPOINT_POLL_MAX_MS / 1000.0
    effective_timeout = max(
        float(settings.CHECKPOINT_WAIT_TIMEOUT_SECONDS),
        float(settings.CHECKPOINT_STALE_SECONDS) + max_delay,
    )
    deadline = _now() + timedelta(seconds=effective_timeout)

    while True:
        async with session_factory() as session:
            await _assert_debate_lease(session, lease)
            cp = await _get_checkpoint(session, lease.debate_id, stage_key)
            if cp is None:
                return "claim"  # disappeared — retry the insert path
            if cp.status == "completed":
                if cp.input_hash == input_hash:
                    return "load"
                # Completed with a different hash — invalidation policy:
                # treat as claimable so the new input produces fresh output.
                return "claim"
            if cp.status in _CLAIMABLE_STATUSES:
                return "claim"
            if cp.status == "running" and cp.owner_id == lease.owner_id:
                raise CheckpointIntegrityError(
                    f"Debate {lease.debate_id}: stage {stage_key} already "
                    f"running under this execution owner — refusing to run twice."
                )
            if cp.status == "running" and _checkpoint_is_stale(cp, now=_now()):
                return "claim"
            # Running under another live owner — keep waiting until it
            # completes or crosses the stale-takeover threshold.

        if _now() >= deadline:
            raise CheckpointIntegrityError(
                f"Debate {lease.debate_id}: stage {stage_key} still locked "
                f"after {effective_timeout}s."
            )
        await asyncio.sleep(delay + random.uniform(0, delay / 2))
        delay = min(max_delay, delay * 2)


async def checkpoint_heartbeat(lease: ExecutionLease, stage_key: str, attempt: int) -> None:
    """Long-stage liveness: refresh heartbeat_at while ownership holds (I).

    A zero-row update means ownership moved — abort by setting the lease-lost
    event; the completion CAS will fail closed as well.
    """
    now = _now()
    stmt = (
        sa.update(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == lease.debate_id)
        .where(DebateStageCheckpoint.stage_key == stage_key)
        .where(DebateStageCheckpoint.status == "running")
        .where(DebateStageCheckpoint.owner_id == lease.owner_id)
        .where(DebateStageCheckpoint.lease_epoch == lease.lease_epoch)
        .where(DebateStageCheckpoint.attempt == attempt)
        .where(_active_debate_lease_exists(lease, now=now))
        .values(heartbeat_at=now, updated_at=now)
    )
    async with async_session_scope() as session:
        result = await session.execute(stmt)
        await session.commit()
    if result.rowcount == 0:
        lease.lease_lost_event.set()
        raise CheckpointOwnershipLostError(
            f"Debate {lease.debate_id}: lost checkpoint ownership for {stage_key}."
        )


async def _conditional_finish(
    lease: ExecutionLease,
    stage_key: str,
    attempt: int,
    input_hash: str,
    *,
    status: str,
    output_reference: Optional[str] = None,
    error: Optional[BaseException] = None,
) -> None:
    """CAS transition to completed/failed (G5/G6)."""
    now = _now()
    values: Dict[str, Any] = dict(
        status=status,
        updated_at=now,
        heartbeat_at=now,
    )
    if status == "completed":
        values["completed_at"] = now
        if output_reference:
            values["output_reference"] = output_reference
    else:
        values["failed_at"] = now
        values["error_message"] = str(error) if error else None
        values["error_code"] = getattr(error, "code", "EXECUTION_ERROR") if error else "EXECUTION_ERROR"

    stmt = (
        sa.update(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == lease.debate_id)
        .where(DebateStageCheckpoint.stage_key == stage_key)
        .where(DebateStageCheckpoint.status == "running")
        .where(DebateStageCheckpoint.owner_id == lease.owner_id)
        .where(DebateStageCheckpoint.lease_epoch == lease.lease_epoch)
        .where(DebateStageCheckpoint.attempt == attempt)
        .where(DebateStageCheckpoint.input_hash == input_hash)
        .where(_active_debate_lease_exists(lease, now=now))
        .values(**values)
    )
    async with async_session_scope() as session:
        # Distinguish "deleted" (integrity error, G7) from "lost ownership".
        cp = await _get_checkpoint(session, lease.debate_id, stage_key)
        result = await session.execute(stmt)
        await session.commit()

    if result.rowcount == 1:
        return
    if cp is None:
        raise CheckpointIntegrityError(
            f"Debate {lease.debate_id}: stage {stage_key} checkpoint "
            "disappeared between execution and completion."
        )
    lease.lease_lost_event.set()
    raise CheckpointOwnershipLostError(
        f"Debate {lease.debate_id}: stage {stage_key} {status} write "
        f"rejected — owned by {cp.owner_id} at epoch {cp.lease_epoch}."
    )


async def _run_unfenced(
    debate_id: str,
    stage_key: str,
    input_hash: str,
    run_fn: Callable[[], Any],
    load_fn: Callable[[Any], Any],
) -> Any:
    """Pre-PS156 checkpoint lifecycle without lease fencing.

    Used only in non-production contexts (tests, offline tooling) where no
    execution lease exists. Production orchestration always goes through the
    fenced path.
    """
    async with async_session_scope() as session:
        checkpoint = await _get_checkpoint(session, debate_id, stage_key)
        if checkpoint:
            if checkpoint.status == "completed" and checkpoint.input_hash == input_hash:
                logger.info(
                    "Debate %s: stage %s already completed with matching hash. Skipping.",
                    debate_id, stage_key,
                )
                return await load_fn(session)
            checkpoint.status = "running"
            checkpoint.input_hash = input_hash
            checkpoint.started_at = _now()
            checkpoint.error_message = None
            checkpoint.error_code = None
            checkpoint.failed_at = None
            checkpoint.attempt = (checkpoint.attempt or 0) + 1
            session.add(checkpoint)
            await session.commit()
        else:
            checkpoint = DebateStageCheckpoint(
                debate_id=debate_id,
                stage_key=stage_key,
                status="running",
                input_hash=input_hash,
                started_at=_now(),
                attempt=1,
            )
            session.add(checkpoint)
            await session.commit()

    try:
        result = await run_fn()

        output_ref = None
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], str)
            and stage_key in {StageKey.SYNTHESIS.value, StageKey.VERIFICATION.value, StageKey.SYNTHESIS_DRAFT.value}
        ):
            actual_result, output_ref = result
        else:
            actual_result = result

        async with async_session_scope() as session:
            checkpoint = await _get_checkpoint(session, debate_id, stage_key)
            if not checkpoint:
                raise CheckpointIntegrityError(
                    f"Debate {debate_id}: stage {stage_key} checkpoint disappeared."
                )
            checkpoint.status = "completed"
            checkpoint.completed_at = _now()
            if output_ref:
                checkpoint.output_reference = output_ref
            session.add(checkpoint)
            await session.commit()

        return actual_result
    except CheckpointIntegrityError:
        raise
    except Exception as exc:
        async with async_session_scope() as session:
            checkpoint = await _get_checkpoint(session, debate_id, stage_key)
            if checkpoint:
                checkpoint.status = "failed"
                checkpoint.error_message = str(exc)
                checkpoint.failed_at = _now()
                checkpoint.error_code = getattr(exc, "code", "EXECUTION_ERROR")
                checkpoint.completed_at = _now()
                session.add(checkpoint)
                await session.commit()
        raise


async def run_with_checkpoint(
    debate_id: str,
    stage_key: str,
    input_data: Dict[str, Any],
    run_fn: Callable[[], Any],
    load_fn: Callable[[Any], Any],
    owner_id: Optional[str] = None,  # legacy positional — prefer execution_lease
    lease_epoch: Optional[int] = None,  # legacy positional
    *,
    execution_lease: Optional[ExecutionLease] = None,
    long_stage: bool = False,
) -> Any:
    """Execute a pipeline stage inside an owner-fenced checkpoint lifecycle.

    ``execution_lease`` may be omitted only when a lease is bound via the
    execution ContextVar. Legacy (owner_id, lease_epoch) pairs are accepted
    for backward compatibility and wrapped into a detached lease object.
    """
    if execution_lease is None and owner_id is not None and lease_epoch is not None:
        execution_lease = ExecutionLease.create(
            debate_id, owner_id=owner_id, lease_epoch=lease_epoch, run_attempt=0
        )
    lease = _resolve_lease(execution_lease)

    serialized = json.dumps(input_data, sort_keys=True, default=str)
    input_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    if lease is None:
        # Legacy unfenced path (local/test only, per Track G1).
        return await _run_unfenced(debate_id, stage_key, input_hash, run_fn, load_fn)
    if lease.debate_id != debate_id:
        raise ValueError("execution_lease.debate_id does not match debate_id")

    # --- Claim phase -------------------------------------------------------
    attempt: Optional[int] = None
    while attempt is None:
        async with async_session_scope() as session:
            await _assert_debate_lease(session, lease)
            cp = await _get_checkpoint(session, debate_id, stage_key)

            if cp is not None:
                if cp.status == "completed" and cp.input_hash == input_hash:
                    logger.info(
                        "checkpoint.reuse debate_id=%s stage=%s attempt=%s",
                        debate_id, stage_key, cp.attempt,
                    )
                    return await load_fn(session)
                if cp.status == "running" and cp.owner_id == lease.owner_id:
                    raise CheckpointIntegrityError(
                        f"Debate {debate_id}: stage {stage_key} already running "
                        "under this execution owner."
                    )
                attempt = await _cas_claim(session, lease, stage_key, input_hash)
                if attempt is not None:
                    await session.commit()
            else:
                attempt = await _insert_new_checkpoint(session, lease, stage_key, input_hash)
                if attempt is not None:
                    await session.commit()

        if attempt is None:
            # Another live owner holds the checkpoint — wait for it.
            action = await _wait_for_checkpoint(async_session_scope, lease, stage_key, input_hash)
            if action == "load":
                async with async_session_scope() as session:
                    return await load_fn(session)
            # action == "claim" — loop around and try the CAS again.

    logger.info(
        "checkpoint.claimed debate_id=%s stage=%s attempt=%s owner=%s epoch=%s",
        debate_id, stage_key, attempt, lease.owner_id, lease.lease_epoch,
    )

    # --- Execute phase -----------------------------------------------------
    heartbeat_task: Optional[asyncio.Task] = None
    if long_stage:
        async def _beat() -> None:
            interval = max(1, int(settings.CHECKPOINT_STALE_SECONDS / 3))
            while True:
                await asyncio.sleep(interval)
                await checkpoint_heartbeat(lease, stage_key, attempt)

        heartbeat_task = asyncio.create_task(_beat())

    try:
        result = await run_fn()

        output_ref = None
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], str)
            and stage_key in {StageKey.SYNTHESIS.value, StageKey.VERIFICATION.value, StageKey.SYNTHESIS_DRAFT.value}
        ):
            actual_result, output_ref = result
        else:
            actual_result = result

        await _conditional_finish(
            lease, stage_key, attempt, input_hash,
            status="completed", output_reference=output_ref,
        )
        return actual_result
    except (ExecutionSupersededError, CheckpointOwnershipLostError, CheckpointIntegrityError):
        raise
    except Exception as exc:
        await _conditional_finish(
            lease, stage_key, attempt, input_hash,
            status="failed", error=exc,
        )
        raise
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, CheckpointOwnershipLostError):
                pass
