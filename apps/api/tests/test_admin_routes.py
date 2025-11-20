import atexit
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
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

from auth import COOKIE_NAME, COOKIE_PATH, create_access_token, hash_password  # noqa: E402
from billing.models import BillingPlan, BillingSubscription, BillingUsage  # noqa: E402
from billing.service import _current_period  # noqa: E402
from database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from models import Debate, User  # noqa: E402
from promotions.models import Promotion  # noqa: E402

init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@dataclass
class SimpleUser:
    id: str
    email: str
    role: str


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
        admin_simple = SimpleUser(id=admin.id, email=admin.email, role=admin.role)
        member_simple = SimpleUser(id=member.id, email=member.email, role=member.role)
        return admin_simple, member_simple


def _set_token(client: TestClient, user: SimpleUser) -> None:
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    client.cookies.set(COOKIE_NAME, token, path=COOKIE_PATH or "/")


def test_admin_endpoints_require_admin(client: TestClient):
    admin, member = _seed_admin_data()
    _set_token(client, member)
    res = client.get("/admin/users")
    assert res.status_code == 403


def test_admin_endpoints_return_payloads(client: TestClient):
    admin, member = _seed_admin_data()
    _set_token(client, admin)

    users_res = client.get("/admin/users")
    assert users_res.status_code == 200
    users_payload = users_res.json()
    assert any(item["email"] == member.email for item in users_payload["items"])

    detail = client.get(f"/admin/users/{member.id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["user"]["email"] == member.email
    assert detail_payload["plan"] and detail_payload["plan"]["slug"] == "free"

    billing = client.get(f"/admin/users/{member.id}/billing")
    assert billing.status_code == 200
    billing_payload = billing.json()
    assert billing_payload["plan"]["slug"] == "free"
    assert billing_payload["usage"]["debates_created"] == 3

    models_res = client.get("/admin/models")
    assert models_res.status_code == 200
    models_payload = models_res.json()
    assert models_payload["items"]

    promotions_res = client.get("/admin/promotions")
    assert promotions_res.status_code == 200
    assert promotions_res.json()["items"]
