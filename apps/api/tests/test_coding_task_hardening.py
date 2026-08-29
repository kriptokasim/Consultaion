import asyncio
from unittest.mock import AsyncMock

import pytest


class _FakeRedisLaneLeases:
    """Tiny async Redis subset for SET NX EX + compare/delete Lua tests."""

    def __init__(self):
        self.values: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def set(self, key, value, *, ex=None, nx=False):
        async with self._lock:
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True

    async def eval(self, _script, _numkeys, key, token):
        async with self._lock:
            if self.values.get(key) == token:
                del self.values[key]
                return 1
            return 0


class _Usage:
    prompt_tokens = 10
    completion_tokens = 20
    total_tokens = 30


def _seed_turn(db_session, *, suffix: str, prompt: str, file_paths=None):
    from models import CodingRun, CodingTurn

    run = CodingRun(
        id=f"run-{suffix}",
        user_id=f"user-{suffix}",
        tier=1,
        file_paths=file_paths or ["main.py"],
        status="running",
    )
    turn = CodingTurn(
        id=f"turn-{suffix}",
        coding_run_id=run.id,
        prompt=prompt,
        status="running",
    )
    db_session.add_all([run, turn])
    db_session.commit()
    return run, turn


@pytest.mark.asyncio
async def test_duplicate_lane_delivery_calls_provider_once(db_session, monkeypatch):
    import redis_pool
    import worker.coding_tasks as coding
    from models import CodingLaneResult
    from sqlmodel import select

    run, turn = _seed_turn(
        db_session,
        suffix="duplicate-lane",
        prompt="Fix the duplicated execution bug",
    )
    redis = _FakeRedisLaneLeases()
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: redis)

    started = asyncio.Event()
    release = asyncio.Event()
    gateway = AsyncMock()

    async def _gateway_once(**_kwargs):
        started.set()
        await release.wait()
        return "patch", _Usage()

    gateway.side_effect = _gateway_once
    monkeypatch.setattr(coding, "call_model_via_gateway", gateway)

    first = asyncio.create_task(
        coding._execute_lane(
            run.id,
            turn.id,
            "fast",
            turn.prompt,
            run_tier=1,
            user_id=run.user_id,
        )
    )
    await started.wait()
    second = asyncio.create_task(
        coding._execute_lane(
            run.id,
            turn.id,
            "fast",
            turn.prompt,
            run_tier=1,
            user_id=run.user_id,
        )
    )

    await asyncio.sleep(0.05)
    assert gateway.await_count == 1

    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert gateway.await_count == 1
    assert first_result.status == "completed"
    assert second_result.status == "completed"
    assert first_result.content == second_result.content == "patch"

    rows = db_session.exec(
        select(CodingLaneResult).where(
            CodingLaneResult.coding_run_id == run.id,
            CodingLaneResult.coding_turn_id == turn.id,
            CodingLaneResult.lane_name == "fast",
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "completed"


@pytest.mark.asyncio
async def test_duplicate_parent_turn_delivery_has_one_finalizer(db_session, monkeypatch):
    import redis_pool
    import worker.coding_tasks as coding
    from database import session_scope
    from models import CodingTurn

    run, turn = _seed_turn(
        db_session,
        suffix="duplicate-parent",
        prompt="Fix parent finalization race",
    )
    redis = _FakeRedisLaneLeases()
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: redis)
    monkeypatch.setattr(coding, "TURN_FOLLOW_POLL_SECONDS", 0.01)

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def _owned_once(run_id: str, turn_id: str):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        with session_scope() as session:
            stored = session.get(CodingTurn, turn_id)
            stored.status = "completed"
            session.add(stored)
            session.commit()

    monkeypatch.setattr(coding, "_async_execute_turn_owned", _owned_once)

    first = asyncio.create_task(coding._async_execute_turn(run.id, turn.id))
    await started.wait()
    second = asyncio.create_task(coding._async_execute_turn(run.id, turn.id))
    await asyncio.sleep(0.03)
    assert calls == 1

    release.set()
    await asyncio.gather(first, second)
    assert calls == 1


@pytest.mark.asyncio
async def test_all_failed_lanes_mark_turn_and_run_failed(db_session, monkeypatch):
    import redis_pool
    import worker.coding_tasks as coding
    from models import CodingPatchArtifact, CodingRun, CodingTurn
    from sqlmodel import select

    run, turn = _seed_turn(
        db_session,
        suffix="all-failed",
        prompt="Fix bug " * 50,
    )

    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: None)
    gateway = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    monkeypatch.setattr(coding, "call_model_via_gateway", gateway)

    await coding._async_execute_turn(run.id, turn.id)

    db_session.expire_all()
    stored_run = db_session.get(CodingRun, run.id)
    stored_turn = db_session.get(CodingTurn, turn.id)
    artifact = db_session.exec(
        select(CodingPatchArtifact).where(
            CodingPatchArtifact.coding_run_id == run.id,
            CodingPatchArtifact.coding_turn_id == turn.id,
        )
    ).first()

    assert stored_run.status == "failed"
    assert stored_turn.status == "failed"
    assert stored_run.error == "Coding Agent produced no successful patch."
    assert artifact is None


@pytest.mark.asyncio
async def test_nonlocal_missing_redis_fails_closed_before_provider(db_session, monkeypatch):
    import redis_pool
    import worker.coding_tasks as coding
    from config import settings

    run, turn = _seed_turn(
        db_session,
        suffix="redis-unavailable",
        prompt="Fix safely",
    )
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: None)
    monkeypatch.setattr(settings, "IS_LOCAL_ENV", False)
    gateway = AsyncMock(return_value=("should not run", _Usage()))
    monkeypatch.setattr(coding, "call_model_via_gateway", gateway)

    result = await coding._execute_lane(
        run.id,
        turn.id,
        "fast",
        turn.prompt,
        run_tier=1,
        user_id=run.user_id,
    )

    assert result.status == "failed"
    assert "coordination" in (result.error or "").lower()
    assert gateway.await_count == 0


@pytest.mark.asyncio
async def test_nonlocal_parent_coordination_unavailable_is_retryable(db_session, monkeypatch):
    import redis_pool
    import worker.coding_tasks as coding
    from config import settings

    run, turn = _seed_turn(
        db_session,
        suffix="parent-redis-unavailable",
        prompt="Do not silently drop parent task",
    )
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: None)
    monkeypatch.setattr(settings, "IS_LOCAL_ENV", False)

    with pytest.raises(coding.LaneCoordinationUnavailable):
        await coding._async_execute_turn(run.id, turn.id)
