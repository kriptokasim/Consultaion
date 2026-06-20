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

fd, temp_path = tempfile.mkstemp(prefix="consultaion_admin_routes_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["RL_MAX_CALLS"] = "1000"
os.environ["AUTH_RL_MAX_CALLS"] = "1000"

sys.path.append(str(Path(__file__).resolve().parents[1]))

import config as config_module  # noqa: E402

config_module.settings.reload()

from auth import get_current_admin, hash_password  # noqa: E402
from billing.models import BillingPlan, BillingSubscription, BillingUsage  # noqa: E402
from billing.service import _current_period  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import AuditLog, Debate, LLMUsageLog, User  # noqa: E402
from promotions.models import Promotion  # noqa: E402
from routes.admin import (  # noqa: E402
    admin_metrics,
    admin_user_billing,
    admin_user_detail,
    admin_users,
)
from schemas import default_panel_config  # noqa: E402

init_db()


def _seed_admin_data():
    with Session(engine) as session:
        plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
        if not plan:
            plan = BillingPlan(slug="free", name="Free", is_default_free=True)
            session.add(plan)
            session.commit()
            session.refresh(plan)
        admin = User(
            id=str(uuid.uuid4()),
            email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("StrongPass#1"),
            is_admin=True,
        )
        member = User(
            id=str(uuid.uuid4()),
            email=f"user-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("StrongPass#2"),
        )
        session.add(admin)
        session.add(member)
        session.commit()
        session.refresh(admin)
        session.refresh(member)
        debate = Debate(
            id=str(uuid.uuid4()),
            prompt="Explain Amber-Mocha oversight.",
            status="completed",
            config={},
            panel_config=default_panel_config().model_dump(),
            engine_version="parliament-v1",
            user_id=member.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(debate)
        usage = BillingUsage(
            user_id=member.id,
            period=_current_period(),
            debates_created=3,
            tokens_used=1500,
            model_tokens={"router-smart": 900, "claude-sonnet": 600},
        )
        session.add(usage)
        subscription = BillingSubscription(
            user_id=member.id,
            plan_id=plan.id,
            status="active",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=15),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=15),
            cancel_at_period_end=False,
            provider="stripe",
        )
        session.add(subscription)
        promo = Promotion(location="dashboard", title="Promo", body="Body copy", is_active=True)
        session.add(promo)
        session.commit()
        return admin.id, member.id, member.email


def test_admin_requires_admin_role():
    admin_id, member_id, _ = _seed_admin_data()
    non_admin_stub = type("Stub", (), {"is_admin": False, "role": "member"})()
    admin_stub = type("Stub", (), {"is_admin": True, "role": "admin"})()
    with pytest.raises(HTTPException):
        get_current_admin(non_admin_stub)
    assert get_current_admin(admin_stub) == admin_stub


def test_admin_payload_helpers_return_data():
    admin_id, member_id, member_email = _seed_admin_data()

    with Session(engine) as session:
        admin_db = session.get(User, admin_id)
        payload = admin_users(q=None, plan_slug=None, limit=100, offset=0, session=session, _=admin_db)
    assert any(item["email"] == member_email for item in payload["items"])

    with Session(engine) as session:
        admin_db = session.get(User, admin_id)
        detail_payload = admin_user_detail(user_id=member_id, session=session, _=admin_db)
    assert detail_payload["user"]["email"] == member_email
    assert detail_payload["plan"]["slug"] == "free"

    with Session(engine) as session:
        admin_db = session.get(User, admin_id)
        billing_payload = admin_user_billing(user_id=member_id, session=session, _=admin_db)
    assert billing_payload["usage"]["debates_created"] == 3

    with Session(engine) as session:
        promo_count = session.exec(select(Promotion)).all()
    assert promo_count


def test_admin_metrics():
    admin_id, member_id, _ = _seed_admin_data()

    # Seed additional logs and data for metrics calculations
    with Session(engine) as session:
        admin_db = session.get(User, admin_id)
        
        # 1. Ensure a pro plan and pro subscription exists
        pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
        if not pro_plan:
            pro_plan = BillingPlan(
                slug="pro",
                name="Pro Plan",
                price_monthly=15.00,
                is_default_free=False
            )
            session.add(pro_plan)
            session.commit()
            session.refresh(pro_plan)

        # Make member_id a pro user
        member = session.get(User, member_id)
        member.plan = "pro"
        session.add(member)

        # Seed active pro subscription
        sub = BillingSubscription(
            user_id=member_id,
            plan_id=pro_plan.id,
            status="active",
            provider="stripe",
            provider_subscription_id=f"sub_metrics_{uuid.uuid4().hex[:6]}",
            provider_customer_id=f"cus_metrics_{uuid.uuid4().hex[:6]}",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(sub)

        # 2. Seed a public debate
        pub_debate = Debate(
            id=str(uuid.uuid4()),
            prompt="Is recursion beautiful?",
            status="completed",
            config={"is_public": True},
            panel_config={},
            user_id=member_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(pub_debate)

        # 3. Seed views and signups from the same IP to test PLG referrals
        view_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        view_log = AuditLog(
            action="view_shared_debate",
            target_type="debate",
            target_id=pub_debate.id,
            meta={"ip_address": "192.168.1.50"},
            created_at=view_time
        )
        session.add(view_log)

        signup_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        signup_log = AuditLog(
            user_id=member_id,
            action="register",
            target_type="user",
            target_id=member_id,
            meta={"ip_address": "192.168.1.50"},
            created_at=signup_time
        )
        session.add(signup_log)

        # 4. Seed LLM usage costs
        usage_log1 = LLMUsageLog(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            cost_usd=0.015,
            success=True,
            created_at=datetime.now(timezone.utc)
        )
        usage_log2 = LLMUsageLog(
            provider="anthropic",
            model="claude-3-5-sonnet",
            prompt_tokens=2000,
            completion_tokens=1000,
            total_tokens=3000,
            cost_usd=0.045,
            success=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(usage_log1)
        session.add(usage_log2)

        session.commit()

        # Invoke admin_metrics
        res = admin_metrics(session=session, _=admin_db)

    # Assert results
    assert "activation" in res
    assert "plg_sharing" in res
    assert "billing_conversion" in res
    assert "economics" in res

    # Activation asserts
    assert res["activation"]["dau"] >= 1
    assert res["activation"]["active_debates"] >= 1

    # PLG asserts
    assert res["plg_sharing"]["public_debates"] >= 1
    assert res["plg_sharing"]["shared_views"] >= 1
    assert res["plg_sharing"]["referred_signups"] >= 1
    assert res["plg_sharing"]["conversion_rate"] > 0.0

    # Billing asserts
    assert res["billing_conversion"]["pro_users"] >= 1
    assert res["billing_conversion"]["subscription_statuses"].get("active", 0) >= 1

    # Economics asserts
    assert res["economics"]["estimated_mrr"] >= 15.00
    assert res["economics"]["cumulative_llm_cost"] >= 0.06
    assert res["economics"]["provider_cost_breakdown"]["openai"] >= 0.015
    assert res["economics"]["provider_cost_breakdown"]["anthropic"] >= 0.045

