import atexit
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, delete, select as sql_select

fd, temp_path = tempfile.mkstemp(prefix="consultaion_promotions_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("JWT_SECRET", "test-secret")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from billing.models import BillingPlan, BillingSubscription  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import User  # noqa: E402
from promotions.models import Promotion  # noqa: E402
from promotions.routes import list_promotions  # noqa: E402


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

init_db()


def _seed_plans():
    with Session(engine) as session:
        plans = session.exec(sql_select(BillingPlan)).all()
        if plans:
            return
        session.add(
            BillingPlan(slug="free", name="Free", is_default_free=True, limits={"max_debates_per_month": 5})
        )
        session.add(
            BillingPlan(slug="pro", name="Pro", price_monthly=29, limits={"max_debates_per_month": 100})
        )
        session.commit()


def _seed_promotions():
    with Session(engine) as session:
        session.exec(delete(Promotion))
        session.add(
            Promotion(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                location="dashboard_sidebar",
                title="Generic",
                body="Welcome",
                cta_label="Go",
                cta_url="/pricing",
                priority=50,
            )
        )
        session.add(
            Promotion(
                id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                location="dashboard_sidebar",
                title="Upgrade",
                body="Get more",
                cta_label="Upgrade",
                cta_url="/settings/billing",
                priority=10,
                target_plan_slug="free",
            )
        )
        session.commit()


def _fetch_promotions(user: User | None):
    with Session(engine) as session:
        result = list_promotions(location="dashboard_sidebar", session=session, current_user=user)
    return result["items"]


def test_promotions_anonymous_gets_generic():
    _seed_plans()
    _seed_promotions()
    items = _fetch_promotions(None)
    assert any(item["title"] == "Generic" for item in items)
    assert all(item["title"] != "Upgrade" for item in items)


def test_promotions_for_free_user_includes_targeted():
    _seed_plans()
    _seed_promotions()
    user = _create_user("promo@free.com")
    titles = {item["title"] for item in _fetch_promotions(user)}
    assert "Upgrade" in titles


def test_promotions_for_pro_user_excludes_free_target():
    _seed_plans()
    _seed_promotions()
    user = _create_user("promo@pro.com")
    with Session(engine) as session:
        plan = session.exec(sql_select(BillingPlan).where(BillingPlan.slug == "pro")).first()
        session.add(
            BillingSubscription(
                user_id=user.id,
                plan_id=plan.id,
                status="active",
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                provider="stripe",
            )
        )
        session.commit()
    titles = {item["title"] for item in _fetch_promotions(user)}
    assert "Upgrade" not in titles
def _create_user(email: str) -> User:
    with Session(engine) as session:
        user = User(id=str(uuid.uuid4()), email=email, password_hash="test", role="user")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
