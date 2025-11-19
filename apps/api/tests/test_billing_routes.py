import atexit
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

fd, temp_path = tempfile.mkstemp(prefix="consultaion_billing_routes_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("JWT_SECRET", "test-secret")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from billing.models import BillingPlan, BillingUsage  # noqa: E402
from billing.routes import CheckoutRequest, create_checkout, get_billing_me, list_billing_plans  # noqa: E402
from billing.service import get_or_create_usage  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import User  # noqa: E402


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

init_db()


def _ensure_plans(session: Session) -> None:
    existing = session.exec(select(BillingPlan)).all()
    if existing:
        return
    session.add(
        BillingPlan(
            slug="free",
            name="Free",
            is_default_free=True,
            limits={"max_debates_per_month": 5, "exports_enabled": True},
        )
    )
    session.add(
        BillingPlan(
            slug="pro",
            name="Pro",
            price_monthly=0.0,
            limits={"max_debates_per_month": 100, "exports_enabled": True},
        )
    )
    session.commit()


def _create_user(session: Session) -> User:
    unique_email = f"billing-{uuid.uuid4().hex}@example.com"
    user = User(id=str(uuid.uuid4()), email=unique_email, password_hash="secret")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_billing_plans_endpoint_lists_seeded_plans():
    with Session(engine) as session:
        _ensure_plans(session)
        payload = list_billing_plans(session=session)
        slugs = [item["slug"] for item in payload["items"]]
        assert "free" in slugs
        assert "pro" in slugs


def test_billing_me_returns_usage_snapshot():
    with Session(engine) as session:
        _ensure_plans(session)
        user = _create_user(session)
        usage = get_or_create_usage(session, user.id)
        usage.debates_created = 2
        session.add(usage)
        session.commit()
        payload = get_billing_me(session=session, current_user=user)
    assert payload["plan"]["slug"] == "free"
    assert payload["usage"]["debates_created"] == 2


def test_billing_checkout_invalid_plan():
    with Session(engine) as session:
        _ensure_plans(session)
        user = _create_user(session)
        with pytest.raises(HTTPException) as exc:
            create_checkout(CheckoutRequest(plan_slug="missing"), session=session, current_user=user)
        assert exc.value.status_code == 404


def test_billing_checkout_uses_provider(monkeypatch):
    class StubProvider:
        def __init__(self):
            self.called = False
            self.url = "https://example.com/test-checkout"

        def create_checkout_session(self, user_id, plan):
            self.called = True
            return self.url

        def handle_webhook(self, payload, headers):
            return None

    stub = StubProvider()

    def fake_get_provider():
        return stub

    with Session(engine) as session:
        _ensure_plans(session)
        user = _create_user(session)
        monkeypatch.setattr("billing.routes.get_billing_provider", fake_get_provider)
        response = create_checkout(CheckoutRequest(plan_slug="free"), session=session, current_user=user)
    assert stub.called
    assert response["checkout_url"] == stub.url
