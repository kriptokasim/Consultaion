# Setup test DB
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from models import Debate, User
from sqlmodel import Session

fd, temp_path = tempfile.mkstemp(prefix="timeline_api_test_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["JWT_SECRET"] = "test-secret"

import config as config_module

config_module.settings.reload()

import database
from auth import create_access_token
from database import init_db, reset_engine
from main import app


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

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_cookies(session):
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email=f"user-{user_id[:8]}@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    # Ensure we use the same secret as the app
    from config import settings
    token = create_access_token(user_id=user.id, email=user.email, role="user")
    return {settings.COOKIE_NAME: token}, user

def test_get_timeline_completed_debate(client, session, auth_cookies):
    cookies, user = auth_cookies
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Test Debate",
        status="completed",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(debate)
    session.commit()

    # Set cookies directly on the request
    response = client.get(f"/debates/{debate_id}/timeline", cookies=cookies)
    assert response.status_code == 200
    events = response.json()
    assert len(events) > 0
    assert events[0]["type"] == "notice"
    assert events[-1]["type"] == "final"

def test_get_timeline_failed_debate(client, session, auth_cookies):
    cookies, user = auth_cookies
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Failed Debate",
        status="failed",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(debate)
    session.commit()

    response = client.get(f"/debates/{debate_id}/timeline", cookies=cookies)
    assert response.status_code == 200
    events = response.json()
    assert len(events) > 0
    assert events[-1]["type"] == "error"

def test_get_timeline_in_progress_debate(client, session, auth_cookies):
    cookies, user = auth_cookies
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Running Debate",
        status="running",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(debate)
    session.commit()

    response = client.get(f"/debates/{debate_id}/timeline", cookies=cookies)
    assert response.status_code == 200

def test_get_timeline_unauthorized(client, session, auth_cookies):
    cookies, user = auth_cookies
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt="Other User Debate",
        status="completed",
        user_id="other-user",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(debate)
    session.commit()

    response = client.get(f"/debates/{debate_id}/timeline", cookies=cookies)
    assert response.status_code == 404 # Not Found (access denied hides existence)

def test_get_timeline_not_found(client, auth_cookies):
    cookies, _ = auth_cookies
    response = client.get(f"/debates/{str(uuid.uuid4())}/timeline", cookies=cookies)
    assert response.status_code == 404
