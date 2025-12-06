import pytest
from sqlmodel import Session, select
from database import engine
from models import Debate, Message
from conversation.engine import run_conversation_debate
from schemas import default_panel_config
from sse_backend import get_sse_backend, reset_sse_backend_for_tests
from config import settings
from orchestrator import run_debate

@pytest.mark.anyio("asyncio")
async def test_conversation_engine_runs_with_mock_llm(db_session):
    panel = default_panel_config()
    debate_id = "conv-run"
    
    debate = Debate(
        id=debate_id,
        prompt="Collaborative discussion on AI safety",
        status="queued",
        panel_config=panel.model_dump(),
        mode="conversation"
    )
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)

    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    await backend.create_channel(f"debate:{debate_id}")
    
    # Enable mode for test
    settings.ENABLE_CONVERSATION_MODE = True
    settings.FAST_DEBATE = False
    
    result = await run_conversation_debate(debate, model_id=None)
    
    assert result.status == "completed"
    assert result.final_answer
    assert result.final_meta["mode"] == "conversation"
    
    # Verify messages
    msgs = db_session.exec(select(Message).where(Message.debate_id == debate_id)).all()
    assert len(msgs) > 0
    assert msgs[0].meta["mode"] == "conversation"

@pytest.mark.anyio("asyncio")
async def test_conversation_engine_respects_flag(db_session):
    panel = default_panel_config()
    debate_id = "conv-flag-test"
    
    debate = Debate(
        id=debate_id,
        prompt="Collaborative discussion on AI safety",
        status="queued",
        panel_config=panel.model_dump(),
        mode="conversation"
    )
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)
    
    # Disable mode
    settings.ENABLE_CONVERSATION_MODE = False
    settings.FAST_DEBATE = False
    
    # run_conversation_debate itself doesn't check the flag, the orchestrator does.
    # The orchestrator catches the exception and marks the debate as failed.
    await run_debate(
        debate_id=debate_id,
        prompt=debate.prompt,
        channel_id="test-channel",
        config_data={}
    )
    
    db_session.refresh(debate)
    assert debate.status == "failed"
    assert "Conversation mode is disabled" in debate.final_meta["error"]
