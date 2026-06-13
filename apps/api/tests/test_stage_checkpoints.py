import pytest
from unittest.mock import AsyncMock
from database_async import async_session_scope
from models import DebateStageCheckpoint
from sqlmodel import select
from orchestration.checkpoints import run_with_checkpoint


@pytest.mark.anyio
async def test_checkpoint_idempotency(db_session):
    debate_id = "test-checkpoint-debate-id"
    stage_key = "test_stage"
    input_data = {"key": "value"}

    run_count = 0

    async def mock_run():
        nonlocal run_count
        run_count += 1
        return f"run-{run_count}"

    async def mock_load(session):
        return "loaded-value"

    # First execution - should run
    res1 = await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data=input_data,
        run_fn=mock_run,
        load_fn=mock_load,
    )

    assert res1 == "run-1"
    assert run_count == 1

    # Verify checkpoint record is created and completed
    async with async_session_scope() as session:
        stmt = (
            select(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .where(DebateStageCheckpoint.stage_key == stage_key)
        )
        res = await session.execute(stmt)
        checkpoint = res.scalars().first()
        assert checkpoint is not None
        assert checkpoint.status == "completed"
        assert checkpoint.input_hash is not None

    # Second execution - should skip run_fn and call load_fn
    res2 = await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data=input_data,
        run_fn=mock_run,
        load_fn=mock_load,
    )

    assert res2 == "loaded-value"
    assert run_count == 1  # Should not have incremented


@pytest.mark.anyio
async def test_checkpoint_input_hash_change(db_session):
    debate_id = "test-hash-debate-id"
    stage_key = "test_stage_hash"
    
    run_count = 0

    async def mock_run():
        nonlocal run_count
        run_count += 1
        return f"val-{run_count}"

    async def mock_load(session):
        return "loaded"

    # Run with first input
    res1 = await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data={"param": 1},
        run_fn=mock_run,
        load_fn=mock_load,
    )
    assert res1 == "val-1"

    # Run with different input - should NOT skip (input_hash changed)
    res2 = await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data={"param": 2},
        run_fn=mock_run,
        load_fn=mock_load,
    )
    assert res2 == "val-2"
    assert run_count == 2
