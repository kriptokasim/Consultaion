import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.mark.anyio
async def test_failed_debate_cannot_be_reacquired(db_session):
    from models import Debate
    from orchestration.execution_lease import acquire_execution_lease

    debate = Debate(
        id="failed-terminal-debate",
        prompt="test",
        status="failed",
        run_attempt=1,
        lease_epoch=3,
    )
    db_session.add(debate)
    db_session.commit()

    result = await acquire_execution_lease(
        debate.id,
        owner_id="stale-worker",
        lease_seconds=60,
    )

    assert result.acquired is False
    db_session.expire_all()
    persisted = db_session.get(Debate, debate.id)
    assert persisted is not None
    assert persisted.status == "failed"
    assert persisted.runner_id is None
    assert persisted.lease_epoch == 3


def test_partial_success_continuation_is_not_refunded(db_session):
    from models import Debate, DebateContinuation
    from services.continuations import transition_continuation_sync

    debate = Debate(
        id="partial-success-debate",
        prompt="test",
        status="completed_with_warnings",
    )
    continuation = DebateContinuation(
        id="partial-success-continuation",
        debate_id=debate.id,
        idempotency_key="partial-success-key",
        status="running",
    )
    db_session.add(debate)
    db_session.add(continuation)
    db_session.commit()

    updated = transition_continuation_sync(
        db_session,
        continuation.id,
        expected_statuses=["running"],
        target_status="failed",
        failure_code="compare_run_failed",
        failure_detail_safe="partial provider failure",
    )

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.failed_at is None
    assert updated.failure_code is None
    assert updated.failure_detail_safe is None


@pytest.mark.anyio
async def test_execution_fenced_sse_rejects_stale_owner(db_session):
    from models import Debate, utcnow
    from orchestration.execution_context import (
        ExecutionLease,
        bind_execution_lease,
        reset_execution_lease,
    )
    from orchestration.execution_lease import ExecutionSupersededError
    from sse_execution_guard import ExecutionFencedSSEBackend

    debate = Debate(
        id="fenced-sse-debate",
        prompt="test",
        status="running",
        runner_id="owner-a",
        execution_owner_id="owner-a",
        lease_epoch=1,
        run_attempt=1,
        lease_expires_at=utcnow().replace(microsecond=0),
    )
    # Ensure the stored lease is initially in the future, then simulate a
    # takeover before the old worker reaches publish().
    from datetime import timedelta

    debate.lease_expires_at = utcnow() + timedelta(minutes=5)
    db_session.add(debate)
    db_session.commit()

    lease = ExecutionLease.create(
        debate.id,
        owner_id="owner-a",
        lease_epoch=1,
        run_attempt=1,
    )

    debate.runner_id = "owner-b"
    debate.execution_owner_id = "owner-b"
    debate.lease_epoch = 2
    db_session.add(debate)
    db_session.commit()

    class Backend:
        def __init__(self):
            self.events = []

        async def publish(self, channel_id, event):
            self.events.append((channel_id, event))

    backend = Backend()
    guarded = ExecutionFencedSSEBackend(backend)
    token = bind_execution_lease(lease)
    try:
        with pytest.raises(ExecutionSupersededError):
            await guarded.publish(
                f"debate:{debate.id}",
                {"type": "model_response_completed", "debate_id": debate.id},
            )
    finally:
        reset_execution_lease(token)

    assert backend.events == []
    assert lease.lease_lost_event.is_set()


@pytest.mark.anyio
async def test_redis_history_gap_is_replayed_before_heartbeat():
    from sse_execution_guard import ExecutionFencedSSEBackend

    terminal = {
        "sequence": 2,
        "type": "debate_completed",
        "payload": {"type": "debate_completed"},
    }
    heartbeat = {
        "sequence": 0,
        "type": "heartbeat",
        "payload": {"type": "heartbeat"},
    }

    class FakeRedis:
        async def get(self, _key):
            return "2"

    class Backend:
        def __init__(self):
            self._redis = FakeRedis()
            self.replay_calls = []

        async def subscribe(self, _channel_id, last_sequence=None):
            yield heartbeat

        async def replay(self, _channel_id, after_sequence=None):
            self.replay_calls.append(after_sequence)
            return [terminal]

    backend = Backend()
    guarded = ExecutionFencedSSEBackend(backend)
    received = []
    async for event in guarded.subscribe("debate:gap", last_sequence=1):
        received.append(event)

    assert received == [terminal]
    assert backend.replay_calls == [1]


@pytest.mark.anyio
async def test_distributed_sse_lease_backend_error_fails_closed(monkeypatch):
    import redis_pool
    import sse_execution_guard as guard
    from config import settings
    from sse_backend import StreamLeaseManager, StreamLeaseResult

    monkeypatch.setattr(guard, "_distributed_sse_leases_required", lambda: True)
    monkeypatch.setattr(settings, "SSE_LEASE_FAIL_OPEN", False, raising=False)
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: None)

    manager = StreamLeaseManager(max_streams=2, lease_ttl=30)
    result = await guard._strict_stream_try_acquire(
        manager,
        "debate-1",
        "subscriber-1",
        "user-1",
    )

    assert result is StreamLeaseResult.ERROR_FAIL_CLOSED


def test_staging_checkpoint_requires_execution_lease(monkeypatch):
    import sse_execution_guard as guard
    from config import settings

    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(guard, "_original_checkpoint_resolve", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="production/staging"):
        guard._strict_checkpoint_resolve(None)


def test_month_bounds_are_calendar_month_not_lifetime():
    from model_gateway.costs import _month_bounds_utc

    start, end = _month_bounds_utc(
        datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
    )

    assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_monthly_cost_check_fails_closed_in_production(monkeypatch):
    from config import settings
    from model_gateway.costs import check_credit_and_cost_safety
    from model_gateway.types import GatewayQuotaExceededError

    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("usage ledger unavailable")

    monkeypatch.setattr(settings, "APP_ENV", "production")

    with pytest.raises(GatewayQuotaExceededError, match="Unable to verify"):
        await check_credit_and_cost_safety(
            user_id="user-1",
            user_plan="free",
            estimated_cost_usd=0.01,
            db_session=BrokenSession(),
        )


@pytest.mark.anyio
async def test_redteam_wrong_json_shape_is_explicitly_incomplete(monkeypatch):
    import orchestration.redteam as redteam

    async def fake_call(*_args, **_kwargs):
        return '{"title":"not-an-array"}', SimpleNamespace()

    monkeypatch.setattr(redteam, "USE_MOCK", False)
    monkeypatch.setattr(redteam, "_call_llm", fake_call)

    result = await redteam.run_red_team_analysis("proposal", ["security"])

    assert len(result) == 1
    assert result[0]["lens"] == "security"
    assert result[0]["title"] == "Incomplete Security review"
    assert "failed" in result[0]["description"].lower()


@pytest.mark.anyio
async def test_concurrent_coding_lanes_use_distinct_sessions(db_session, monkeypatch):
    from models import CodingRun, CodingTurn
    from worker import coding_tasks

    run = CodingRun(user_id="coding-user", tier=1, file_paths=["main.py"])
    db_session.add(run)
    db_session.commit()
    turn = CodingTurn(coding_run_id=run.id, prompt="Fix production bug")
    db_session.add(turn)
    db_session.commit()

    session_ids = []

    async def fake_gateway(*_args, **kwargs):
        session_ids.append(id(kwargs["db_session"]))
        await asyncio.sleep(0.02)
        return "patch", SimpleNamespace(
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )

    monkeypatch.setattr(coding_tasks, "call_model_via_gateway", fake_gateway)

    results = await asyncio.gather(
        coding_tasks._execute_lane(
            run.id,
            turn.id,
            "fast",
            turn.prompt,
            run_tier=1,
            user_id=run.user_id,
        ),
        coding_tasks._execute_lane(
            run.id,
            turn.id,
            "thinking",
            turn.prompt,
            run_tier=1,
            user_id=run.user_id,
        ),
    )

    assert {result.status for result in results} == {"completed"}
    assert len(session_ids) == 2
    assert len(set(session_ids)) == 2
