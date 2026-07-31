from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import Debate, Message, User
from orchestrator import run_debate
from sqlmodel import select

from config import settings


def _prepare_postgres_integration(db_session, user_id: str) -> None:
    from database import engine

    if engine.url.get_backend_name() != "postgresql":
        pytest.skip("multi-session orchestration integration requires PostgreSQL")
    db_session.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test"))
    db_session.commit()


@pytest.mark.anyio
async def test_arena_run_integration(db_session, monkeypatch):
    # Set FAST_DEBATE to False so we run the real arena flow
    monkeypatch.setattr(settings, "FAST_DEBATE", False)
    # Streaming/progressive synthesis are covered separately; keep this orchestration
    # integration test on its patched, deterministic non-streaming path.
    monkeypatch.setattr(settings, "STREAMING_RESPONSES_ENABLED", False)
    monkeypatch.setattr(settings, "ARENA_PROGRESSIVE_SYNTHESIS_ENABLED", False)

    # Setup
    debate_id = "test-arena-debate"
    user_id = "test-user-id"
    prompt = "Why is water wet?"
    _prepare_postgres_integration(db_session, user_id)

    # Create Debate record
    debate = Debate(
        id=debate_id,
        user_id=user_id,
        prompt=prompt,
        status="queued",
        mode="arena",
        config={}
    )
    db_session.add(debate)
    db_session.commit()

    # Mock LLM response helper class
    class MockUsage:
        def __init__(self, tokens=100):
            self.prompt_tokens = 20
            self.completion_tokens = tokens - 20
            self.total_tokens = tokens
            self.cost_usd = 0.001
            self.provider = "mock"
            self.model = "mock-model"
        def to_dict(self):
            return {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd": self.cost_usd
            }

    async def mock_call(*args, **kwargs):
        role = kwargs.get("role", "")
        if "Synthesizer" in role:
            return "Synthesized arena verdict.", MockUsage(150)
        return f"Mock answer from SOTA model for role {role}.", MockUsage(100)

    mock_report = MagicMock()
    mock_report.executive_summary = "Synthesized arena verdict."
    mock_report.title = "Decision Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {"mock": "report"}

    # Patch LLM caller, email sender, and SSE backend
    with patch("arena.engine.call_llm_for_role", side_effect=mock_call), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("orchestrator._build_and_send_summary", new_callable=AsyncMock), \
         patch("orchestrator.get_sse_backend") as mock_get_backend:

        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend

        # Execute the debate run via orchestrator
        await run_debate(
            debate_id=debate_id,
            prompt=prompt,
            channel_id=f"debate:{debate_id}",
            config_data={}
        )

        # Expire all cached objects in the test session to force fresh DB fetch
        db_session.expire_all()

        # Verify DB updates
        updated_debate = db_session.exec(select(Debate).where(Debate.id == debate_id)).first()
        assert updated_debate is not None
        assert updated_debate.status == "completed"
        assert updated_debate.final_content == "Synthesized arena verdict."
        assert updated_debate.final_meta["successful_count"] == 4

        # Verify SSE publish events occurred
        assert mock_backend.publish.call_count > 0


@pytest.mark.anyio
async def test_compare_run_integration(db_session, monkeypatch):
    # Set FAST_DEBATE to False so we run the real compare flow
    monkeypatch.setattr(settings, "FAST_DEBATE", False)

    # Setup
    debate_id = "test-compare-debate"
    user_id = "test-user-id"
    prompt = "Rust vs Go"
    _prepare_postgres_integration(db_session, user_id)

    # Create Debate record with compare models
    debate = Debate(
        id=debate_id,
        user_id=user_id,
        prompt=prompt,
        status="queued",
        mode="compare",
        config={"compare_models": ["gpt4o-mini", "claude-haiku"]}
    )
    db_session.add(debate)
    db_session.commit()

    class MockUsage:
        def __init__(self, tokens=100):
            self.prompt_tokens = 20
            self.completion_tokens = tokens - 20
            self.total_tokens = tokens
            self.cost_usd = 0.001
            self.provider = "mock"
            self.model = "mock-model"
        def to_dict(self):
            return {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd": self.cost_usd
            }

    async def mock_call(*args, **kwargs):
        role = kwargs.get("role", "")
        return f"Mock compare answer for role {role}.", MockUsage(100)

    # Patch LLM caller, email sender, and SSE backend
    with patch("agents.call_llm_for_role", side_effect=mock_call), \
         patch("orchestrator._build_and_send_summary", new_callable=AsyncMock), \
         patch("orchestrator.get_sse_backend") as mock_get_backend:

        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend

        # Execute compare run
        await run_debate(
            debate_id=debate_id,
            prompt=prompt,
            channel_id=f"debate:{debate_id}",
            config_data={"compare_models": ["gpt4o-mini", "claude-haiku"]}
        )

        db_session.expire_all()

        # Verify DB updates
        updated_debate = db_session.exec(select(Debate).where(Debate.id == debate_id)).first()
        assert updated_debate is not None
        assert updated_debate.status == "completed"

        # Verify model messages were persisted
        messages = db_session.exec(select(Message).where(Message.debate_id == debate_id)).all()
        assert len(messages) >= 2
