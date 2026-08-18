import atexit
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

fd, temp_path = tempfile.mkstemp(prefix="consultaion_billing_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("DISABLE_AUTORUN", "1")
os.environ.setdefault("DISABLE_RATINGS", "1")
os.environ.setdefault("FAST_DEBATE", "1")
os.environ.setdefault("RL_MAX_CALLS", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import hash_password  # noqa: E402
from billing.models import BillingPlan, BillingSubscription  # noqa: E402
from billing.service import (  # noqa: E402
    add_tokens_usage,
    get_active_plan,
    get_or_create_usage,
    increment_debate_usage,
    increment_export_usage,
)
from database import engine, init_db  # noqa: E402
from models import User  # noqa: E402

_DB_PATH = test_db_path


def _cleanup():
    try:
        if _DB_PATH.exists():
            _DB_PATH.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

init_db()


def _ensure_default_plan(session: Session) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
    if plan:
        plan.limits = {"max_debates_per_month": 1, "exports_enabled": False}
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan
    plan = BillingPlan(
        slug="free",
        name="Free",
        is_default_free=True,
        limits={"max_debates_per_month": 1, "exports_enabled": False},
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def _ensure_pro_plan(session: Session) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    if plan:
        return plan
    plan = BillingPlan(
        slug="pro",
        name="Pro",
        is_default_free=False,
        limits={"max_debates_per_month": 100, "exports_enabled": True},
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def _create_user(session: Session, prefix: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("StrongPass#Billing1"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_billing_usage_helpers_enforce_limits():
    if os.getenv("FASTAPI_TEST_MODE") == "1":
        pytest.skip("Billing limits bypassed under FASTAPI_TEST_MODE")
    user_id = "user-123"
    with Session(engine) as session:
        plan = _ensure_default_plan(session)
        active_plan = get_active_plan(session, user_id)
        assert active_plan.id == plan.id
        assert active_plan.limits.get("max_debates_per_month") == 1

        usage = get_or_create_usage(session, user_id)
        assert usage.debates_created == 0

        usage = increment_debate_usage(session, user_id)
        assert usage.debates_created == 1
        with pytest.raises(HTTPException):
            increment_debate_usage(session, user_id)

        with pytest.raises(HTTPException):
            increment_export_usage(session, user_id)

        usage = add_tokens_usage(session, user_id, "router-smart", 500)
        assert usage.tokens_used == 500
        usage = add_tokens_usage(session, user_id, "router-smart", 250)
        assert usage.tokens_used == 750
        assert usage.model_tokens["router-smart"] == 750


def test_future_active_subscription_does_not_grant_entitlement():
    with Session(engine) as session:
        free = _ensure_default_plan(session)
        pro = _ensure_pro_plan(session)
        user = _create_user(session, "future-sub")
        now = datetime.now(timezone.utc)
        session.add(
            BillingSubscription(
                user_id=user.id,
                plan_id=pro.id,
                status="active",
                provider="test",
                current_period_start=now + timedelta(days=2),
                current_period_end=now + timedelta(days=32),
            )
        )
        session.commit()

        assert get_active_plan(session, user.id).id == free.id


def test_expired_active_subscription_does_not_grant_entitlement():
    with Session(engine) as session:
        free = _ensure_default_plan(session)
        pro = _ensure_pro_plan(session)
        user = _create_user(session, "expired-sub")
        now = datetime.now(timezone.utc)
        session.add(
            BillingSubscription(
                user_id=user.id,
                plan_id=pro.id,
                status="active",
                provider="test",
                current_period_start=now - timedelta(days=32),
                current_period_end=now - timedelta(days=2),
            )
        )
        session.commit()

        assert get_active_plan(session, user.id).id == free.id


def test_current_trialing_subscription_grants_entitlement():
    with Session(engine) as session:
        _ensure_default_plan(session)
        pro = _ensure_pro_plan(session)
        user = _create_user(session, "trialing-sub")
        now = datetime.now(timezone.utc)
        session.add(
            BillingSubscription(
                user_id=user.id,
                plan_id=pro.id,
                status="trialing",
                provider="stripe",
                current_period_start=now - timedelta(minutes=1),
                current_period_end=now + timedelta(days=14),
            )
        )
        session.commit()

        assert get_active_plan(session, user.id).id == pro.id
