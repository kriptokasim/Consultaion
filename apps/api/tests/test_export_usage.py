"""
Tests for export usage persistence.

Verifies that export usage increments are properly committed to the database
and that failed exports don't increment usage counters.

Patchset 52.0
"""

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["RL_MAX_CALLS"] = "1000"
os.environ["DISABLE_AUTORUN"] = "1"

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
from auth import hash_password  # noqa: E402
from billing.models import BillingPlan, BillingUsage  # noqa: E402
from billing.service import _current_period, get_or_create_usage  # noqa: E402
from models import Debate, DebateRound, Message, Score, User  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


@pytest.fixture
def client():
    """Test client for making API requests."""
    from main import app
    return TestClient(app)


def _ensure_plan(session: Session) -> None:
    """Ensure a default billing plan exists."""
    existing = session.exec(select(BillingPlan)).first()
    if existing:
        return
    session.add(
        BillingPlan(
            slug="free",
            name="Free",
            is_default_free=True,
            limits={"max_debates_per_month": 100, "exports_enabled": True},
        )
    )
    session.commit()


def test_export_usage_is_incremented_and_persisted(client):
    """Test that export usage is incremented and persisted to database."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email="export_test@example.com",
            password_hash=hash_password("password123"),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create completed debate
        debate_id = str(uuid.uuid4())
        debate = Debate(
            id=debate_id,
            prompt="Export test prompt that is sufficiently long for validation",
            status="completed",
            user_id=user.id,
            model_id="router-smart",
            config={},
            final_content="Test final content for export",
        )
        session.add(debate)
        session.commit()
        
        # Check initial usage
        initial_usage = get_or_create_usage(session, user.id)
        initial_exports = initial_usage.exports_count
    
    # Login
    login_response = client.post(
        "/auth/login",
        json={"email": "export_test@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Export debate
    response = client.post(f"/debates/{debate_id}/export")
    
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    
    # Verify usage was incremented and persisted
    with Session(database.engine) as session:
        final_usage = get_or_create_usage(session, user.id)
        assert final_usage.exports_count == initial_exports + 1


def test_csv_export_usage_is_persisted(client):
    """Test that CSV export usage is also persisted."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email="csv_export@example.com",
            password_hash=hash_password("password123"),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create completed debate with scores
        debate_id = str(uuid.uuid4())
        debate = Debate(
            id=debate_id,
            prompt="CSV export test prompt that is sufficiently long",
            status="completed",
            user_id=user.id,
            model_id="router-smart",
            config={},
        )
        session.add(debate)
        session.commit()
        
        # Add some scores
        score = Score(
            debate_id=debate_id,
            persona="TestAgent",
            judge="TestJudge",
            score=8.5,
            rationale="Test rationale",
        )
        session.add(score)
        session.commit()
        
        # Check initial usage
        initial_usage = get_or_create_usage(session, user.id)
        initial_exports = initial_usage.exports_count
    
    # Login
    login_response = client.post(
        "/auth/login",
        json={"email": "csv_export@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Export CSV
    response = client.get(f"/debates/{debate_id}/scores.csv")
    
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    
    # Verify usage was incremented
    with Session(database.engine) as session:
        final_usage = get_or_create_usage(session, user.id)
        assert final_usage.exports_count == initial_exports + 1


def test_export_usage_not_incremented_on_failure(client):
    """Test that export usage is not incremented if export fails."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email="export_fail@example.com",
            password_hash=hash_password("password123"),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Check initial usage
        initial_usage = get_or_create_usage(session, user.id)
        initial_exports = initial_usage.exports_count
    
    # Login
    login_response = client.post(
        "/auth/login",
        json={"email": "export_fail@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Try to export non-existent debate
    fake_debate_id = str(uuid.uuid4())
    response = client.post(f"/debates/{fake_debate_id}/export")
    
    # Should fail with 404
    assert response.status_code == 404
    
    # Verify usage was NOT incremented
    with Session(database.engine) as session:
        final_usage = get_or_create_usage(session, user.id)
        assert final_usage.exports_count == initial_exports


def test_multiple_exports_increment_correctly(client):
    """Test that multiple exports correctly increment the counter."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email="multi_export@example.com",
            password_hash=hash_password("password123"),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create two completed debates
        debate1_id = str(uuid.uuid4())
        debate1 = Debate(
            id=debate1_id,
            prompt="First debate for multiple exports test that is long enough",
            status="completed",
            user_id=user.id,
            model_id="router-smart",
            config={},
            final_content="First debate content",
        )
        
        debate2_id = str(uuid.uuid4())
        debate2 = Debate(
            id=debate2_id,
            prompt="Second debate for multiple exports test also long enough",
            status="completed",
            user_id=user.id,
            model_id="router-smart",
            config={},
            final_content="Second debate content",
        )
        
        session.add(debate1)
        session.add(debate2)
        session.commit()
        
        # Check initial usage
        initial_usage = get_or_create_usage(session, user.id)
        initial_exports = initial_usage.exports_count
    
    # Login
    login_response = client.post(
        "/auth/login",
        json={"email": "multi_export@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Export first debate
    response1 = client.post(f"/debates/{debate1_id}/export")
    assert response1.status_code == 200
    
    # Export second debate
    response2 = client.post(f"/debates/{debate2_id}/export")
    assert response2.status_code == 200
    
    # Verify usage incremented by 2
    with Session(database.engine) as session:
        final_usage = get_or_create_usage(session, user.id)
        assert final_usage.exports_count == initial_exports + 2
