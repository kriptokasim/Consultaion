import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import database
import pytest
from models import Debate, Message
from parliament.timeline import build_debate_timeline
from sqlmodel import Session

# Setup test DB
fd, temp_path = tempfile.mkstemp(prefix="timeline_test_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

import config as config_module

config_module.settings.reload()

from database import init_db, reset_engine


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    reset_engine()
    init_db()
    yield
    try:
        test_db_path.unlink()
    except OSError:
        pass

@pytest.fixture
def session():
    with Session(database.engine) as session:
        yield session

def test_build_timeline_completed_debate(session):
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Test Debate",
        status="completed",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        updated_at=datetime.now(timezone.utc),
        user_id="user1"
    )
    session.add(debate)
    
    # Add messages
    msg1 = Message(
        debate_id=debate_id,
        role="seat",
        persona="Pro",
        content="Argument 1",
        round_index=0,
        created_at=debate.created_at + timedelta(minutes=1),
        meta={"seat_id": "seat1", "role_profile": "debater", "provider": "openai", "model": "gpt-4"}
    )
    msg2 = Message(
        debate_id=debate_id,
        role="seat",
        persona="Con",
        content="Argument 2",
        round_index=0,
        created_at=debate.created_at + timedelta(minutes=2),
        meta={"seat_id": "seat2", "role_profile": "debater", "provider": "anthropic", "model": "claude-3"}
    )
    session.add(msg1)
    session.add(msg2)
    session.commit()
    session.refresh(debate)

    timeline = build_debate_timeline(session, debate)
    
    assert len(timeline) >= 5 # Init, Round Start, Msg1, Msg2, Round End, Completed
    
    # Check types
    types = [e.type for e in timeline]
    assert "system_notice" in types # Init
    assert "round_start" in types
    assert "seat_message" in types
    assert "round_end" in types
    assert "debate_completed" in types
    
    # Check sorting
    assert timeline[0].ts <= timeline[-1].ts
    
    # Check message details
    msg_event = next(e for e in timeline if e.type == "seat_message" and e.seat_label == "Pro")
    assert msg_event.provider == "openai"
    assert msg_event.model == "gpt-4"
    assert msg_event.content == "Argument 1"

def test_build_timeline_failed_debate(session):
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Failed Debate",
        status="failed",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        updated_at=datetime.now(timezone.utc),
        final_meta={"error": "API Error"},
        user_id="user1"
    )
    session.add(debate)
    session.commit()
    
    timeline = build_debate_timeline(session, debate)
    
    assert len(timeline) >= 2 # Init, Failed
    assert timeline[-1].type == "debate_failed"
    assert timeline[-1].meta["reason"] == "API Error"
