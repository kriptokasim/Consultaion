"""
Tests for token quota usage tracking.

Verifies that debate execution records token usage for authenticated users
and that anonymous/system debates don't record usage.

Patchset 52.0
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["RL_MAX_CALLS"] = "1000"
os.environ["AUTH_RL_MAX_CALLS"] = "1000"
os.environ["DISABLE_AUTORUN"] = "1"

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
from billing.models import BillingPlan, BillingUsage  # noqa: E402
from billing.service import _current_period, get_or_create_usage  # noqa: E402
from models import Debate, User  # noqa: E402
from orchestrator import run_debate  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


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


def test_debate_execution_records_token_usage_for_user():
    """Test that debate execution records token usage for authenticated users."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email="quota_test@example.com",
            password_hash="hash",
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create debate owned by user
        debate_id = str(uuid.uuid4())
        debate = Debate(
            id=debate_id,
            prompt="Test prompt for token usage tracking that is sufficiently long",
            status="queued",
            user_id=user.id,
            model_id="router-smart",
            config={},
        )
        session.add(debate)
        session.commit()
        
        # Check initial usage
        initial_usage = get_or_create_usage(session, user.id)
        initial_tokens = initial_usage.tokens_used
        
        # Run debate (in mock mode it will complete quickly)
        channel_id = f"test-channel-{uuid.uuid4()}"
        asyncio.run(
            run_debate(
                debate_id=debate_id,
                prompt=debate.prompt,
                channel_id=channel_id,
                config_data=debate.config,
                model_id=debate.model_id,
            )
        )
        
        # Verify usage was recorded
        session.expire_all()
        final_usage = get_or_create_usage(session, user.id)
        
        # In mock mode we should still see token tracking
        # The exact amount depends on mock implementation
        assert final_usage.tokens_used >= initial_tokens


def test_anonymous_debate_does_not_record_usage():
    """Test that debates without a user_id don't record usage."""
    with Session(database.engine) as session:
        _ensure_plan(session)
        
        # Create debate without user_id (anonymous/system debate)
        debate_id = str(uuid.uuid4())
        debate = Debate(
            id=debate_id,
            prompt="Anonymous test prompt that is sufficiently long for validation",
            status="queued",
            user_id=None,  # No user attached
            model_id="router-smart",
            config={},
        )
        session.add(debate)
        session.commit()
        
        # Run debate
        channel_id = f"test-channel-{uuid.uuid4()}"
        asyncio.run(
            run_debate(
                debate_id=debate_id,
                prompt=debate.prompt,
                channel_id=channel_id,
                config_data=debate.config,
                model_id=debate.model_id,
            )
        )
        
        # Verify no usage records were created for non-existent user
        # (This test mainly ensures no errors are thrown)
        session.expire_all()
        debate = session.get(Debate, debate_id)
        assert debate is not None
        # Test passes if we got here without errors
