import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from config import settings
from models import Debate, Message
from orchestrator import run_debate
from sqlmodel import select

@pytest.mark.anyio
async def test_arena_run_integration(db_session, monkeypatch):
    # Set FAST_DEBATE to False so we run the real arena flow
    monkeypatch.setattr(settings, "FAST_DEBATE", False)
    
    # Setup
    debate_id = "test-arena-debate"
    user_id = "test-user-id"
    prompt = "Why is water wet?"
    
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
        return f"Side-by-side comparison response for {role}.", MockUsage(100)

    # Patch LLM caller and SSE backend
    with patch("compare.engine.call_llm_for_role", side_effect=mock_call), \
         patch("orchestrator.get_sse_backend") as mock_get_backend:
         
        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend
        
        # Execute the compare run via orchestrator
        await run_debate(
            debate_id=debate_id,
            prompt=prompt,
            channel_id=f"debate:{debate_id}",
            config_data={"compare_models": ["gpt4o-mini", "claude-haiku"]}
        )
        
        # Expire all cached objects in the test session to force fresh DB fetch
        db_session.expire_all()
        
        # Verify DB updates
        updated_debate = db_session.exec(select(Debate).where(Debate.id == debate_id)).first()
        assert updated_debate is not None
        assert updated_debate.status == "completed"
        assert "Side-by-side comparison response" in updated_debate.final_content
        
        # Verify SSE publish events occurred
        assert mock_backend.publish.call_count > 0
        
        # Verify Messages are persisted
        messages = db_session.exec(select(Message).where(Message.debate_id == debate_id)).all()
        assert len(messages) == 2
        for msg in messages:
            assert msg.role == "seat"
            assert msg.meta["mode"] == "compare"


@pytest.mark.anyio
async def test_conversation_run_integration(db_session, monkeypatch):
    # Set FAST_DEBATE to False so we run the real conversation flow
    monkeypatch.setattr(settings, "FAST_DEBATE", False)
    monkeypatch.setattr(settings, "ENABLE_CONVERSATION_MODE", True)

    # Setup
    debate_id = "test-conversation-debate"
    user_id = "test-user-id"
    prompt = "Let's discuss Next.js"
    
    # Create Debate record with conversation mode
    debate = Debate(
        id=debate_id,
        user_id=user_id,
        prompt=prompt,
        status="queued",
        mode="conversation",
        config={},
        panel_config={
            "seats": [
                {"seat_id": "seat-1", "display_name": "Agent A", "model": "gpt-4o", "temperature": 0.7}
            ]
        }
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
        return f"Conversation reply from {role}.", MockUsage(100)

    # Patch LLM caller, email sender, and SSE backend
    with patch("conversation.engine.call_llm_for_role", side_effect=mock_call), \
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
        assert "Conversation reply" in updated_debate.final_content
        
        # Verify SSE publish events occurred
        assert mock_backend.publish.call_count > 0
        
        # Verify Messages are persisted
        messages = db_session.exec(select(Message).where(Message.debate_id == debate_id)).all()
        assert len(messages) > 0


@pytest.mark.anyio
async def test_parliament_run_integration(db_session, monkeypatch):
    # Set FAST_DEBATE to False so we run the real parliament flow
    monkeypatch.setattr(settings, "FAST_DEBATE", False)

    # Setup
    debate_id = "test-parliament-debate"
    user_id = "test-user-id"
    prompt = "Is AI good?"
    
    # Create Debate record with parliament configuration
    debate = Debate(
        id=debate_id,
        user_id=user_id,
        prompt=prompt,
        status="queued",
        mode="parliament",
        config={},
        panel_config={
            "seats": [
                {"seat_id": "p-1", "display_name": "Proponent", "role_profile": "optimist", "model": "gpt-4o", "temperature": 0.5},
                {"seat_id": "p-2", "display_name": "Opponent", "role_profile": "pessimist", "model": "gpt-4o", "temperature": 0.5}
            ]
        }
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
        # If the evaluator/judge is called, return scoring JSON
        if "Judge" in role:
            return '{"scores": [{"persona": "Proponent", "score": 8.0, "rationale": "good"}, {"persona": "Opponent", "score": 7.5, "rationale": "fine"}]}', MockUsage(120)
        return f"Parliament speech from {role}.", MockUsage(100)

    # Patch LLM caller, email sender, and SSE backend
    with patch("parliament.engine.call_llm_for_role", side_effect=mock_call), \
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
        assert "Parliament speech" in updated_debate.final_content
        
        # Verify SSE publish events occurred
        assert mock_backend.publish.call_count > 0
        
        # Verify Messages are persisted
        messages = db_session.exec(select(Message).where(Message.debate_id == debate_id)).all()
        assert len(messages) > 0

