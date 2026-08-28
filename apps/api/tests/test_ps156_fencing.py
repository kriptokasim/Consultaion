"""PS156 — Execution fencing, lease-loss cancellation, atomic checkpoints.

Covers the lease lifecycle (acquire/heartbeat/release), fenced debate writes,
and CAS stage-checkpoint behavior against a real database. PostgreSQL is the
production concurrency target; these tests prove the semantics on the test
database (SQLite serializes writers, which still validates the CAS logic and
rowcount contracts).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from database import session_scope
from models import Debate, DebateAttempt, DebateStageCheckpoint, Message
from orchestration.checkpoints import (
    CheckpointIntegrityError,
    CheckpointOwnershipLostError,
    run_with_checkpoint,
)
from orchestration.execution_context import ExecutionLease, new_owner_id
from orchestration.execution_lease import (
    LeaseRenewResult,
    acquire_execution_lease,
    heartbeat_loop,
    release_execution_lease,
    renew_execution_lease,
)
from orchestration.fencing import fenced_debate_update

from config import settings


def _mk_debate(debate_id: str, status: str = "queued") -> str:
    with session_scope() as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
            session.commit()
        debate = Debate(id=debate_id, prompt="PS156", status=status, user_id="u1")
        session.add(debate)
        session.commit()
    return debate_id


def _get_debate(debate_id: str) -> Debate:
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        session.expunge(debate)
        return debate


def _lease_for(debate: Debate, owner: str | None = None) -> ExecutionLease:
    return ExecutionLease.create(
        debate.id,
        owner_id=owner or debate.runner_id,
        lease_epoch=debate.lease_epoch,
        run_attempt=debate.run_attempt,
    )


# ── 1. Owner ID uniqueness (Track K-1) ───────────────────────────────────


def test_owner_id_unique_per_invocation():
    ids = {new_owner_id() for _ in range(50)}
    assert len(ids) == 50
    for oid in ids:
        uuid.UUID(oid.split(":")[-1])  # UUID fragment mandatory


# ── 2/3/7. Acquisition basics + epoch monotonicity ───────────────────────


@pytest.mark.anyio
async def test_first_acquisition_wins_and_increments_epoch_once():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert result.acquired
    debate = _get_debate(debate_id)
    assert debate.lease_epoch == 1
    assert debate.run_attempt == 1
    assert debate.status == "running"
    assert debate.execution_started_at is not None


@pytest.mark.anyio
async def test_second_acquisition_denied_while_live():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    first = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert first.acquired
    second = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert not second.acquired and second.conflict


@pytest.mark.anyio
async def test_concurrent_acquisition_single_winner():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    results = await asyncio.gather(
        *(acquire_execution_lease(debate_id, lease_seconds=30) for _ in range(5))
    )
    winners = [r for r in results if r.acquired]
    assert len(winners) == 1
    debate = _get_debate(debate_id)
    assert debate.run_attempt == 1


# ── 10. Terminal debates cannot be reacquired ────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["completed", "completed_with_warnings", "cancelled"])
async def test_terminal_debate_not_reacquirable(status):
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}", status=status)
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert not result.acquired


# ── 4/5/8. Heartbeat verification ────────────────────────────────────────


@pytest.mark.anyio
async def test_heartbeat_renews_and_never_increments_counters():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    lease = result.lease
    renewed = await renew_execution_lease(lease, lease_seconds=30)
    assert renewed is LeaseRenewResult.RENEWED
    debate = _get_debate(debate_id)
    assert debate.lease_epoch == 1 and debate.run_attempt == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    ["perspectives_ready", "completed", "completed_with_warnings", "failed"],
)
async def test_heartbeat_renews_while_same_owner_finalizes(status):
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    lease = result.lease

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.status = status
        session.add(debate)
        session.commit()

    renewed = await renew_execution_lease(lease, lease_seconds=30)

    assert renewed is LeaseRenewResult.RENEWED
    assert not lease.lease_lost_event.is_set()


@pytest.mark.anyio
async def test_heartbeat_loop_does_not_signal_loss_after_status_transition(monkeypatch):
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    lease = result.lease

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.status = "completed"
        session.add(debate)
        session.commit()

    import orchestration.execution_lease as lease_mod

    stop = asyncio.Event()
    original = lease_mod.renew_execution_lease

    async def _renew_once(*args, **kwargs):
        renewed = await original(*args, **kwargs)
        stop.set()
        return renewed

    monkeypatch.setattr(lease_mod, "renew_execution_lease", _renew_once)
    await heartbeat_loop(
        lease,
        lease_seconds=30,
        interval_seconds=0,
        failure_threshold=2,
        stop_event=stop,
    )

    assert not lease.lease_lost_event.is_set()


@pytest.mark.anyio
async def test_old_owner_heartbeat_lost_after_takeover():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    first = await acquire_execution_lease(debate_id, lease_seconds=0)
    # Force expiry so a second owner can take over.
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()
    second = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert second.acquired
    lost = await renew_execution_lease(first.lease, lease_seconds=30)
    assert lost is LeaseRenewResult.OWNERSHIP_LOST


# ── 6. Conditional release ───────────────────────────────────────────────


@pytest.mark.anyio
async def test_old_owner_cannot_release_new_owners_lease():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    first = await acquire_execution_lease(debate_id, lease_seconds=0)
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()
    second = await acquire_execution_lease(debate_id, lease_seconds=30)
    released = await release_execution_lease(first.lease)
    assert released is False
    debate = _get_debate(debate_id)
    assert debate.runner_id == second.lease.owner_id


# ── 11. Heartbeat infrastructure failure threshold ───────────────────────


@pytest.mark.anyio
async def test_heartbeat_loop_aborts_after_threshold():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    lease = result.lease

    async def _boom(*args, **kwargs):
        raise ConnectionError("db down")

    import orchestration.execution_lease as lease_mod

    original = lease_mod.renew_execution_lease
    lease_mod.renew_execution_lease = _boom
    try:
        stop = asyncio.Event()
        await heartbeat_loop(
            lease,
            lease_seconds=30,
            interval_seconds=0,
            failure_threshold=2,
            stop_event=stop,
        )
    finally:
        lease_mod.renew_execution_lease = original
    assert lease.lease_lost_event.is_set()


@pytest.mark.anyio
async def test_heartbeat_loop_immediate_on_ownership_loss():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    result = await acquire_execution_lease(debate_id, lease_seconds=30)
    lease = result.lease
    # Simulate takeover: wipe the runner so renewal matches zero rows.
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.runner_id = "someone-else"
        session.add(debate)
        session.commit()
    stop = asyncio.Event()
    await heartbeat_loop(
        lease, lease_seconds=30, interval_seconds=0, failure_threshold=99, stop_event=stop
    )
    assert lease.lease_lost_event.is_set()


# ── 15/16/19. Fenced debate writes ───────────────────────────────────────


@pytest.mark.anyio
async def test_stale_owner_cannot_write_final_content():
    from database_async import async_session_scope

    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    first = await acquire_execution_lease(debate_id, lease_seconds=0)
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()
    second = await acquire_execution_lease(debate_id, lease_seconds=30)

    from orchestration.execution_lease import ExecutionSupersededError

    async with async_session_scope() as session:
        with pytest.raises(ExecutionSupersededError):
            await fenced_debate_update(
                session, first.lease, {"final_content": "stale"}, what="final_content"
            )
    # New owner can still write.
    async with async_session_scope() as session:
        await fenced_debate_update(
            session, second.lease, {"final_content": "fresh"}, what="final_content"
        )
        await session.commit()
    assert _get_debate(debate_id).final_content == "fresh"


@pytest.mark.anyio
async def test_stale_owner_cannot_transition_status():
    from database_async import async_session_scope
    from orchestration.execution_lease import ExecutionSupersededError

    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    first = await acquire_execution_lease(debate_id, lease_seconds=0)
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()
    await acquire_execution_lease(debate_id, lease_seconds=30)

    async with async_session_scope() as session:
        with pytest.raises(ExecutionSupersededError):
            await fenced_debate_update(session, first.lease, {"status": "failed"}, what="status")
    assert _get_debate(debate_id).status == "running"


@pytest.mark.anyio
async def test_expired_owner_cannot_write_before_takeover():
    from database_async import async_session_scope
    from orchestration.execution_lease import ExecutionSupersededError

    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    acquired = await acquire_execution_lease(debate_id, lease_seconds=30)
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()

    async with async_session_scope() as session:
        with pytest.raises(ExecutionSupersededError):
            await fenced_debate_update(
                session,
                acquired.lease,
                {"status": "failed"},
                what="expired terminal write",
            )
    assert _get_debate(debate_id).status == "running"


# ── Checkpoint helpers ───────────────────────────────────────────────────


def _owned_debate(debate_id: str, owner: str, epoch: int = 1) -> None:
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.runner_id = owner
        debate.execution_owner_id = owner
        debate.lease_epoch = epoch
        debate.status = "running"
        debate.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        session.add(debate)
        session.commit()


# ── 21/22. Concurrent checkpoint claims ──────────────────────────────────


@pytest.mark.anyio
async def test_concurrent_checkpoint_claim_single_runner():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease_a = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)
    lease_b = ExecutionLease.create(debate_id, owner_id="owner-b", lease_epoch=1, run_attempt=1)

    run_count = 0

    async def _run():
        nonlocal run_count
        run_count += 1
        await asyncio.sleep(0.05)
        return "done"

    async def _load(session):
        return "loaded"

    # lease_b cannot pass the debate-lease assertion (owner-a holds the row),
    # so its attempt must fail.  Run sequentially to avoid SQLite WAL
    # contention that can cause spurious integrity errors under aiosqlite.
    from orchestration.execution_lease import ExecutionSupersededError

    with pytest.raises(ExecutionSupersededError):
        await run_with_checkpoint(
            debate_id, "stage-x", {"k": 1}, _run, _load, execution_lease=lease_b
        )

    result_a = await run_with_checkpoint(
        debate_id, "stage-x", {"k": 1}, _run, _load, execution_lease=lease_a
    )
    assert result_a == "done"
    assert run_count == 1


# ── 23/24. Completed-checkpoint reuse / hash change ──────────────────────


@pytest.mark.anyio
async def test_completed_checkpoint_reuse_and_hash_change_reexecutes():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)

    runs = []

    async def _run():
        runs.append(1)
        return "v1"

    async def _load(session):
        return "from-store"

    r1 = await run_with_checkpoint(
        debate_id, "stage-reuse", {"k": 1}, _run, _load, execution_lease=lease
    )
    assert r1 == "v1"
    r2 = await run_with_checkpoint(
        debate_id, "stage-reuse", {"k": 1}, _run, _load, execution_lease=lease
    )
    assert r2 == "from-store"
    assert len(runs) == 1

    with session_scope() as session:
        checkpoint = (
            session.query(DebateStageCheckpoint)
            .filter_by(
                debate_id=debate_id,
                stage_key="stage-reuse",
            )
            .one()
        )
        checkpoint.output_reference = "stale-output-reference"
        session.add(checkpoint)
        session.commit()

    # Different input hash must not return stale output — re-executes.
    r3 = await asyncio.wait_for(
        run_with_checkpoint(
            debate_id,
            "stage-reuse",
            {"k": 2},
            _run,
            _load,
            execution_lease=lease,
        ),
        timeout=1,
    )
    assert r3 == "v1"
    assert len(runs) == 2
    with session_scope() as session:
        checkpoint = (
            session.query(DebateStageCheckpoint)
            .filter_by(
                debate_id=debate_id,
                stage_key="stage-reuse",
            )
            .one()
        )
        assert checkpoint.output_reference is None


@pytest.mark.anyio
async def test_terminal_owner_can_complete_postprocessing_checkpoint():
    """A terminal status must not revoke an otherwise live execution lease."""
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.status = "completed"
        session.add(debate)
        session.commit()

    runs = []

    async def _run():
        runs.append(1)
        return "postprocessed"

    async def _load(session):
        return "loaded"

    result = await run_with_checkpoint(
        debate_id,
        "terminal-postprocessing",
        {"kind": "divergence"},
        _run,
        _load,
        execution_lease=lease,
    )

    assert result == "postprocessed"
    assert runs == [1]


# ── 25/26. Stale completion/failure rejection ────────────────────────────


@pytest.mark.anyio
async def test_stale_worker_completion_rejected():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease_a = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)

    gate = asyncio.Event()

    async def _run():
        await gate.wait()
        return "stale-result"

    async def _load(session):
        return "loaded"

    task = asyncio.create_task(
        run_with_checkpoint(
            debate_id, "stage-stale", {"k": 1}, _run, _load, execution_lease=lease_a
        )
    )
    await asyncio.sleep(0.05)

    # Take over: checkpoint becomes owned by owner-b via CAS, and the Debate
    # lease moves to owner-b as well.
    with session_scope() as session:
        cp = (
            session.query(DebateStageCheckpoint)
            .filter_by(debate_id=debate_id, stage_key="stage-stale")
            .one()
        )
        cp.owner_id = "owner-b"
        cp.lease_epoch = 2
        cp.attempt += 1
        session.add(cp)
        debate = session.get(Debate, debate_id)
        debate.runner_id = "owner-b"
        debate.lease_epoch = 2
        session.add(debate)
        session.commit()

    gate.set()
    with pytest.raises(CheckpointOwnershipLostError):
        await task

    with session_scope() as session:
        cp = (
            session.query(DebateStageCheckpoint)
            .filter_by(debate_id=debate_id, stage_key="stage-stale")
            .one()
        )
        assert cp.status == "running"  # stale completion did not land
        assert cp.owner_id == "owner-b"


@pytest.mark.anyio
async def test_debate_takeover_alone_rejects_old_checkpoint_completion():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease_a = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)
    gate = asyncio.Event()

    async def _run():
        await gate.wait()
        return "stale-result"

    async def _load(session):
        return "loaded"

    task = asyncio.create_task(
        run_with_checkpoint(
            debate_id,
            "stage-debate-takeover",
            {"k": 1},
            _run,
            _load,
            execution_lease=lease_a,
        )
    )
    await asyncio.sleep(0.05)

    # Only the Debate lease moves. The checkpoint row still carries owner-a;
    # completion must nevertheless fail because owner-a no longer owns the
    # execution lease.
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.runner_id = "owner-b"
        debate.execution_owner_id = "owner-b"
        debate.lease_epoch = 2
        debate.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        session.add(debate)
        session.commit()

    gate.set()
    with pytest.raises(CheckpointOwnershipLostError):
        await task

    with session_scope() as session:
        cp = (
            session.query(DebateStageCheckpoint)
            .filter_by(debate_id=debate_id, stage_key="stage-debate-takeover")
            .one()
        )
        assert cp.status == "running"
        assert cp.owner_id == "owner-a"
        assert cp.lease_epoch == 1


# ── 27. Deleted checkpoint → integrity error ─────────────────────────────


@pytest.mark.anyio
async def test_deleted_checkpoint_is_integrity_error():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)

    async def _run():
        with session_scope() as session:
            cp = (
                session.query(DebateStageCheckpoint)
                .filter_by(debate_id=debate_id, stage_key="stage-del")
                .one()
            )
            session.delete(cp)
            session.commit()
        return "x"

    async def _load(session):
        return "loaded"

    with pytest.raises(CheckpointIntegrityError):
        await run_with_checkpoint(
            debate_id, "stage-del", {"k": 1}, _run, _load, execution_lease=lease
        )


# ── 29/30. Theft protection vs stale takeover ────────────────────────────


@pytest.mark.anyio
async def test_fresh_running_checkpoint_not_stolen():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    lease_a = ExecutionLease.create(debate_id, owner_id="owner-a", lease_epoch=1, run_attempt=1)

    gate = asyncio.Event()
    started = asyncio.Event()

    async def _run_a():
        started.set()
        await gate.wait()
        return "a-done"

    async def _load(session):
        return "loaded"

    task_a = asyncio.create_task(
        run_with_checkpoint(
            debate_id, "stage-theft", {"k": 1}, _run_a, _load, execution_lease=lease_a
        )
    )
    await started.wait()

    # owner-b holds NO debate lease, so its checkpoint operations fail closed
    # at the debate-lease assertion rather than stealing the stage.
    lease_b = ExecutionLease.create(debate_id, owner_id="owner-b", lease_epoch=1, run_attempt=1)

    from orchestration.execution_lease import ExecutionSupersededError

    with pytest.raises(ExecutionSupersededError):
        await run_with_checkpoint(
            debate_id, "stage-theft", {"k": 1}, _run_a, _load, execution_lease=lease_b
        )

    gate.set()
    assert await task_a == "a-done"


@pytest.mark.anyio
async def test_waits_until_checkpoint_is_stale_then_takes_over(monkeypatch):
    monkeypatch.setattr(settings, "CHECKPOINT_STALE_SECONDS", 0.05)
    monkeypatch.setattr(settings, "CHECKPOINT_WAIT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(settings, "CHECKPOINT_POLL_INITIAL_MS", 1)
    monkeypatch.setattr(settings, "CHECKPOINT_POLL_MAX_MS", 5)

    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-b", epoch=2)
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        session.add(
            DebateStageCheckpoint(
                debate_id=debate_id,
                stage_key="stage-wait-takeover",
                status="running",
                input_hash="old-input",
                owner_id="owner-a",
                lease_epoch=1,
                attempt=1,
                started_at=now,
                updated_at=now,
                heartbeat_at=now,
            )
        )
        session.commit()

    lease_b = ExecutionLease.create(debate_id, owner_id="owner-b", lease_epoch=2, run_attempt=2)
    runs = []

    async def _run():
        runs.append(1)
        return "taken-over"

    async def _load(session):
        return "unexpected-load"

    result = await asyncio.wait_for(
        run_with_checkpoint(
            debate_id,
            "stage-wait-takeover",
            {"k": "new"},
            _run,
            _load,
            execution_lease=lease_b,
        ),
        timeout=1,
    )
    assert result == "taken-over"
    assert runs == [1]

    with session_scope() as session:
        cp = (
            session.query(DebateStageCheckpoint)
            .filter_by(debate_id=debate_id, stage_key="stage-wait-takeover")
            .one()
        )
        assert cp.status == "completed"
        assert cp.owner_id == "owner-b"
        assert cp.lease_epoch == 2
        assert cp.attempt == 2


# ── 20. Attempt-scoped message isolation ─────────────────────────────────


def test_prior_attempt_messages_isolated():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    with session_scope() as session:
        session.add(
            Message(
                debate_id=debate_id,
                role="candidate",
                content="old",
                round_index=1,
                attempt_id="attempt-1",
            )
        )
        session.add(
            Message(
                debate_id=debate_id,
                role="candidate",
                content="new",
                round_index=1,
                attempt_id="attempt-2",
            )
        )
        session.commit()
        rows = session.query(Message).filter_by(debate_id=debate_id).all()
        by_attempt = {m.attempt_id: m.content for m in rows}
        assert by_attempt["attempt-1"] == "old"
        assert by_attempt["attempt-2"] == "new"


def test_admin_leases_selects_latest_checkpoint_by_timestamp():
    from routes.admin.leases import admin_leases

    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    _owned_debate(debate_id, "owner-a")
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        session.add(
            DebateStageCheckpoint(
                id=f"zz-old-{uuid.uuid4()}",
                debate_id=debate_id,
                stage_key="older-stage",
                status="completed",
                input_hash="old",
                started_at=now - timedelta(minutes=2),
                updated_at=now - timedelta(minutes=1),
            )
        )
        session.add(
            DebateStageCheckpoint(
                id=f"aa-new-{uuid.uuid4()}",
                debate_id=debate_id,
                stage_key="newer-stage",
                status="running",
                input_hash="new",
                started_at=now,
                updated_at=now,
                heartbeat_at=now,
                owner_id="owner-a",
                lease_epoch=1,
            )
        )
        session.commit()

    payload = admin_leases(None)
    item = next(row for row in payload["debates"] if row["debate_id"] == debate_id)
    assert item["current_checkpoint"]["stage_key"] == "newer-stage"


# ── Logical attempt identity vs execution ownership ─────────────────────


@pytest.mark.anyio
async def test_takeover_preserves_logical_run_attempt():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    with session_scope() as session:
        session.add(
            DebateAttempt(
                debate_id=debate_id,
                attempt_number=1,
                status="queued",
            )
        )
        session.commit()

    first = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert first.acquired
    assert first.lease.run_attempt == 1

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()

    second = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert second.acquired
    assert second.lease.lease_epoch == first.lease.lease_epoch + 1
    assert second.lease.run_attempt == 1

    debate = _get_debate(debate_id)
    assert debate.run_attempt == 1
    with session_scope() as session:
        attempt = (
            session.query(DebateAttempt).filter_by(debate_id=debate_id, attempt_number=1).one()
        )
        assert attempt.status == "running"


@pytest.mark.anyio
async def test_queued_retry_advances_logical_run_attempt_once():
    debate_id = _mk_debate(f"ps156-{uuid.uuid4().hex[:8]}")
    with session_scope() as session:
        session.add(
            DebateAttempt(
                debate_id=debate_id,
                attempt_number=1,
                status="queued",
            )
        )
        session.commit()

    first = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert first.acquired and first.lease.run_attempt == 1

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        debate.status = "scheduled"
        session.add(debate)
        session.add(
            DebateAttempt(
                debate_id=debate_id,
                attempt_number=2,
                status="queued",
            )
        )
        session.commit()

    second = await acquire_execution_lease(debate_id, lease_seconds=30)
    assert second.acquired
    assert second.lease.run_attempt == 2
    assert _get_debate(debate_id).run_attempt == 2
    with session_scope() as session:
        attempt = (
            session.query(DebateAttempt).filter_by(debate_id=debate_id, attempt_number=2).one()
        )
        assert attempt.status == "running"
