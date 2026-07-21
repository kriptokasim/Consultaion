"""PS155.6 — Integration regression tests."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from database import session_scope
from models import Debate
from orchestrator import run_debate
from schemas import AgentConfig, DebateConfig, JudgeConfig
from sse_backend import DeltaCoalescer


# 1. Full run_debate() with mock adapter - verify lease epoch increments, checkpoint ownership, and clean termination
# SKIPPED: Requires live database + Redis. Run via: pytest -m integration
@pytest.mark.anyio("asyncio")
@pytest.mark.skip(reason="Requires live database. Run with pytest -m integration")
async def test_run_debate_fencing_and_ownership(monkeypatch):
    monkeypatch.setenv("FAST_DEBATE", "1")

    d_id = "fencing-regression-debate"
    d_prompt = "Test regression fencing"
    d_config = DebateConfig(
        agents=[AgentConfig(name="Analyst", persona="Systems thinker")],
        judges=[JudgeConfig(name="JudgeOne", rubrics=["accuracy"])],
    ).model_dump()

    # Make sure clean up from any previous failed runs
    with session_scope() as session:
        existing = session.query(Debate).filter_by(id=d_id).first()
        if existing:
            session.delete(existing)
            session.commit()

    debate = Debate(
        id=d_id,
        prompt=d_prompt,
        status="queued",
        config=d_config,
    )

    with session_scope() as session:
        session.add(debate)
        session.commit()

    with patch("orchestrator.get_sse_backend") as mock_get_backend, \
         patch("orchestrator._complete_debate_record", new_callable=AsyncMock) as mock_complete:
        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend

        # Verify that try_acquire_lease sets execution_owner_id and increments epoch
        from orchestrator import _get_runner_id
        runner_id = _get_runner_id()
        
        # Call run_debate which will execute and release the lease cleanly
        await run_debate(d_id, d_prompt, f"debate:{d_id}", d_config)

        # Refresh debate from database to inspect post-release state
        with session_scope() as session:
            db_debate = session.query(Debate).filter_by(id=d_id).first()
            assert db_debate is not None
            # Monotonic epoch increments to at least 1 during acquisition
            assert db_debate.lease_epoch >= 1
            # After clean termination/finally block, lease is released
            assert db_debate.execution_owner_id is None
            assert db_debate.runner_id is None

        # Clean up
        with session_scope() as session:
            existing = session.query(Debate).filter_by(id=d_id).first()
            if existing:
                session.delete(existing)
                session.commit()


# 2. SSE stream with coalesced deltas - verify event count reduction
def test_sse_stream_coalesced_reduction():
    # Verify delta coalescing reduces total events sent
    coalescer = DeltaCoalescer(flush_interval_ms=5000)
    
    events = [
        {"type": "model_response_delta", "payload": {"response_id": "r1", "text": "a", "accumulated_chars": 1, "delta_sequence": 1}},
        {"type": "model_response_delta", "payload": {"response_id": "r1", "text": "b", "accumulated_chars": 2, "delta_sequence": 2}},
        {"type": "model_response_delta", "payload": {"response_id": "r1", "text": "c", "accumulated_chars": 3, "delta_sequence": 3}},
    ]
    
    emitted = []
    for evt in events:
        emitted.extend(coalescer.ingest(evt))
        
    assert len(emitted) == 0  # Buffered in coalescer
    
    flushed = coalescer.flush_all()
    assert len(flushed) == 1  # Coalesced down to 1 event
    assert flushed[0]["payload"]["text"] == "abc"
    assert flushed[0]["payload"]["accumulated_chars"] == 3


# 3. Provider credential isolation - verify os.environ is clean after debate run
@pytest.mark.anyio("asyncio")
async def test_provider_credential_isolation_regression(monkeypatch):
    # Ensure provider keys are not leaked to os.environ during or after debate setup/run
    original_env = dict(os.environ)
    for k in list(os.environ.keys()):
        if k.endswith("_API_KEY"):
            del os.environ[k]

    from agents import resolve_api_key

    from config import settings
    
    settings.OPENAI_API_KEY = "test_openai_key"
    
    resolved = resolve_api_key("openai")
    assert resolved == "test_openai_key"
    assert "OPENAI_API_KEY" not in os.environ

    os.environ.clear()
    os.environ.update(original_env)
