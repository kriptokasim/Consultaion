import atexit
import os
import sys
import tempfile
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

from billing.models import BillingPlan  # noqa: E402
from billing.service import (  # noqa: E402
    add_tokens_usage,
    get_active_plan,
    get_or_create_usage,
    increment_debate_usage,
    increment_export_usage,
)
from database import engine, init_db  # noqa: E402

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


def test_billing_usage_helpers_enforce_limits():
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
