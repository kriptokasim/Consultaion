import pytest
import json
from unittest.mock import AsyncMock, patch
from database_async import async_session_scope
from models import User, Debate, DebateStageCheckpoint, Message, Score, Vote, DivergenceReport
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


@pytest.mark.anyio
async def test_checkpoint_attempt_and_output_ref(db_session):
    debate_id = "test-attempt-ref-debate-id"
    stage_key = "synthesis"
    input_data = {"data": "test"}

    run_count = 0
    async def mock_run():
        nonlocal run_count
        run_count += 1
        return "result-value", "output-ref-value"

    async def mock_load(session):
        return "loaded-value"

    # First run
    await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data=input_data,
        run_fn=mock_run,
        load_fn=mock_load,
    )

    async with async_session_scope() as session:
        stmt = select(DebateStageCheckpoint).where(
            DebateStageCheckpoint.debate_id == debate_id,
            DebateStageCheckpoint.stage_key == stage_key
        )
        ckpt = (await session.execute(stmt)).scalars().first()
        assert ckpt.attempt == 1
        assert ckpt.output_reference == "output-ref-value"

    # Set status to failed to force rerun
    async with async_session_scope() as session:
        stmt_edit = select(DebateStageCheckpoint).where(
            DebateStageCheckpoint.debate_id == debate_id,
            DebateStageCheckpoint.stage_key == stage_key
        )
        res = await session.execute(stmt_edit)
        ckpt = res.scalars().first()
        ckpt.status = "failed"
        session.add(ckpt)
        await session.commit()

    # Second run
    await run_with_checkpoint(
        debate_id=debate_id,
        stage_key=stage_key,
        input_data=input_data,
        run_fn=mock_run,
        load_fn=mock_load,
    )

    async with async_session_scope() as session:
        stmt_check = select(DebateStageCheckpoint).where(
            DebateStageCheckpoint.debate_id == debate_id,
            DebateStageCheckpoint.stage_key == stage_key
        )
        res = await session.execute(stmt_check)
        ckpt = res.scalars().first()
        assert ckpt.attempt == 2


@pytest.mark.anyio
async def test_retry_api_downstream_clearing(authenticated_client, db_session):
    # Retrieve authenticated user
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()

    # Create a debate
    debate = Debate(
        id="test-retry-debate",
        user_id=user.id,
        prompt="Test retry prompt",
        status="completed",
    )
    db_session.add(debate)

    # Add checkpoints
    ckpts = [
        DebateStageCheckpoint(debate_id=debate.id, stage_key="draft", status="completed", input_hash="dummy"),
        DebateStageCheckpoint(debate_id=debate.id, stage_key="critique", status="completed", input_hash="dummy"),
        DebateStageCheckpoint(debate_id=debate.id, stage_key="judge", status="completed", input_hash="dummy"),
        DebateStageCheckpoint(debate_id=debate.id, stage_key="synthesis_draft", status="completed", input_hash="dummy"),
        DebateStageCheckpoint(debate_id=debate.id, stage_key="verification", status="completed", input_hash="dummy"),
        DebateStageCheckpoint(debate_id=debate.id, stage_key="synthesis", status="completed", input_hash="dummy"),
    ]
    for c in ckpts:
        db_session.add(c)

    # Add entities
    db_session.add(Message(debate_id=debate.id, role="candidate", content="Draft answer", round_index=1))
    db_session.add(Message(debate_id=debate.id, role="revised", content="Critique answer", round_index=2))
    db_session.add(Score(debate_id=debate.id, persona="Model", judge="Judge1", score=9.0, rationale="Great"))
    db_session.add(Vote(debate_id=debate.id, method="plurality", rankings={"order": []}))
    db_session.add(Message(debate_id=debate.id, role="synthesizer", content="Final synthesis", round_index=3))
    db_session.add(DivergenceReport(debate_id=debate.id, divergence_score=0.5))

    db_session.commit()

    # We retry the "judge" stage
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/retry",
            json={"stage_key": "judge"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        assert response.json()["retried_stage"] == "judge"
        mock_dispatch.assert_called_once()

    # Verify that:
    # 1. "judge", "synthesis_draft", "verification", and "synthesis" checkpoints are deleted
    # 2. "draft" and "critique" checkpoints are preserved
    # 3. Scores, votes, synthesizer messages are deleted, but candidate and revised messages are preserved.
    db_session.expire_all()

    # Check checkpoints
    res_ckpts = db_session.exec(
        select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate.id)
    ).all()
    remaining_keys = {c.stage_key for c in res_ckpts}
    assert "draft" in remaining_keys
    assert "critique" in remaining_keys
    assert "judge" not in remaining_keys
    assert "synthesis_draft" not in remaining_keys
    assert "verification" not in remaining_keys
    assert "synthesis" not in remaining_keys

    # Check entities
    candidates = db_session.exec(select(Message).where(Message.debate_id == debate.id).where(Message.role == "candidate")).all()
    assert len(candidates) == 1

    revised = db_session.exec(select(Message).where(Message.debate_id == debate.id).where(Message.role == "revised")).all()
    assert len(revised) == 1

    scores = db_session.exec(select(Score).where(Score.debate_id == debate.id)).all()
    assert len(scores) == 0

    votes = db_session.exec(select(Vote).where(Vote.debate_id == debate.id)).all()
    assert len(votes) == 0

    synthesizers = db_session.exec(select(Message).where(Message.debate_id == debate.id).where(Message.role == "synthesizer")).all()
    assert len(synthesizers) == 0


@pytest.mark.anyio
async def test_debate_workspace_serialization(db_session):
    # Setup test objects in db
    from models import Debate, DebateStageCheckpoint, Message, Score
    from serializers import serialize_debate_public, serialize_debate_private

    debate = Debate(
        id="test-workspace-serialization",
        prompt="Who should manage workspace state?",
        status="running",
        mode="arena",
        config={"agents": [{"name": "A", "persona": "P"}], "is_public": True},
    )
    db_session.add(debate)

    # Checkpoints
    ck1 = DebateStageCheckpoint(debate_id=debate.id, stage_key="arena_perspectives", status="completed", input_hash="h1")
    ck2 = DebateStageCheckpoint(debate_id=debate.id, stage_key="divergence_analysis", status="running", input_hash="h2")
    db_session.add(ck1)
    db_session.add(ck2)

    # Messages and Scores
    msg1 = Message(debate_id=debate.id, role="arena_response", content="Response 1", round_index=1)
    db_session.add(msg1)
    
    score1 = Score(debate_id=debate.id, persona="Model", judge="Judge1", score=8.5, rationale="Nice")
    db_session.add(score1)

    db_session.commit()
    db_session.refresh(debate)

    # Perform public serialization
    serialized_pub = serialize_debate_public(debate, session=db_session)
    assert serialized_pub["current_stage"] == "divergence_analysis"
    assert serialized_pub["responses_received"] == 1
    assert serialized_pub["scores_received"] == 1
    assert serialized_pub["models_expected"] == 4  # Default for arena
    assert len(serialized_pub["stage_checkpoints"]) == 2
    assert serialized_pub["synthesis_error"] is None  # Excluded from public DTO

    # Perform private serialization
    serialized_priv = serialize_debate_private(debate, session=db_session)
    assert serialized_priv["current_stage"] == "divergence_analysis"
    assert serialized_priv["responses_received"] == 1
    assert serialized_priv["scores_received"] == 1
    assert serialized_priv["models_expected"] == 4
    assert len(serialized_priv["stage_checkpoints"]) == 2

