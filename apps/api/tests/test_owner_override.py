import pytest
from sqlmodel import Session, select
from models import User
from billing.models import BillingPlan
from billing.service import get_active_plan
from usage_limits import reserve_run_slot, RateLimitError
from config import settings
from tests.utils import settings_context

def test_get_active_plan_owner_override(db_session: Session):
    # Setup a user
    user = User(email="owner@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Use settings_context to override the allowlist
    with settings_context(OWNER_EMAIL_ALLOWLIST=user.email, OWNER_PLAN="pro"):
        plan = get_active_plan(db_session, user.id)
        assert plan is not None
        assert plan.slug == "pro"

def test_get_active_plan_normal_user_free(db_session: Session):
    # Setup a user
    user = User(email="normal_test@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Use settings_context to ensure allowlist doesn't include this user
    with settings_context(OWNER_EMAIL_ALLOWLIST="someoneelse@example.com"):
        plan = get_active_plan(db_session, user.id)
        assert plan is not None
        assert plan.is_default_free == True

def test_reserve_run_slot_bypasses_quota_for_owner(db_session: Session):
    # Setup a user
    user = User(email="owner_bypass@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Use settings_context to override allowlist and unlimited flag
    with settings_context(
        OWNER_EMAIL_ALLOWLIST=user.email, 
        OWNER_UNLIMITED="True", 
        DEFAULT_MAX_RUNS_PER_HOUR="0"
    ):
        # Should NOT raise because is_owner bypasses it
        reserve_run_slot(db_session, user.id)
        
        # Now try as if they AREN'T an owner (should raise)
        with settings_context(OWNER_EMAIL_ALLOWLIST="notme@example.com"):
            with pytest.raises(RateLimitError):
                reserve_run_slot(db_session, user.id)
