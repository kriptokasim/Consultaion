import os
import tempfile
from pathlib import Path
import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session

# Setup temp DB
fd, temp_path = tempfile.mkstemp(prefix="consultaion_usage_test_", suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = f"sqlite:///{temp_path}"

import config
config.settings.reload()

import database
from models import User, UsageQuota, UsageCounter
from usage_limits import (
    _get_or_create_quota,
    _get_or_reset_counter,
    _ensure_daily_token_headroom,
    reserve_run_slot,
    record_token_usage,
    RateLimitError
)

@pytest.fixture(autouse=True)
def setup_db():
    database.reset_engine()
    database.init_db()

@pytest.fixture
def db_session():
    with Session(database.engine) as session:
        yield session
        session.rollback()

@pytest.fixture
def test_user(db_session):
    user = User(email="test_usage_coverage@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

def test_get_or_create_quota(db_session, test_user):
    # Test hour quota creation
    quota = _get_or_create_quota(db_session, test_user.id, "hour")
    assert quota.period == "hour"
    assert quota.max_runs is not None
    
    # Test existing quota retrieval
    quota2 = _get_or_create_quota(db_session, test_user.id, "hour")
    assert quota2.id == quota.id
    
    # Test day quota creation
    quota_day = _get_or_create_quota(db_session, test_user.id, "day")
    assert quota_day.period == "day"
    assert quota_day.max_tokens is not None

def test_get_or_reset_counter(db_session, test_user):
    # Test new counter
    counter = _get_or_reset_counter(db_session, test_user.id, "hour")
    assert counter.runs_used == 0
    
    # Test existing counter within window
    counter.runs_used = 5
    db_session.add(counter)
    db_session.commit()
    
    counter2 = _get_or_reset_counter(db_session, test_user.id, "hour")
    assert counter2.id == counter.id
    assert counter2.runs_used == 5
    
    # Test reset after window
    counter.window_start = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.add(counter)
    db_session.commit()
    
    counter3 = _get_or_reset_counter(db_session, test_user.id, "hour")
    assert counter3.runs_used == 0

def test_ensure_daily_token_headroom(db_session, test_user):
    # Should pass when usage is low
    _ensure_daily_token_headroom(db_session, test_user.id)
    
    # Should raise when limit exceeded
    quota = _get_or_create_quota(db_session, test_user.id, "day")
    quota.max_tokens = 100
    db_session.add(quota)
    db_session.commit()
    
    counter = _get_or_reset_counter(db_session, test_user.id, "day")
    counter.tokens_used = 150
    db_session.add(counter)
    db_session.commit()
    
    with pytest.raises(RateLimitError) as exc:
        _ensure_daily_token_headroom(db_session, test_user.id)
    assert exc.value.code == "tokens_per_day"

def test_reserve_run_slot(db_session, test_user):
    # Should succeed
    reserve_run_slot(db_session, test_user.id)
    
    # Should raise when limit exceeded
    quota = _get_or_create_quota(db_session, test_user.id, "hour")
    quota.max_runs = 1
    db_session.add(quota)
    db_session.commit()
    
    # Already used 1 slot above
    with pytest.raises(RateLimitError) as exc:
        reserve_run_slot(db_session, test_user.id)
    assert exc.value.code == "runs_per_hour"

def test_record_token_usage(db_session, test_user):
    record_token_usage(db_session, test_user.id, 100)
    
    counter = _get_or_reset_counter(db_session, test_user.id, "day")
    assert counter.tokens_used == 100
    
    # Test with None session (should use session_scope)
    record_token_usage(None, test_user.id, 50)
    
    db_session.refresh(counter)
    assert counter.tokens_used == 150

def test_record_token_usage_no_user(db_session):
    # Should do nothing
    record_token_usage(db_session, None, 100)
