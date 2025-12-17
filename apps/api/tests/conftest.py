import os

import pytest

# Simplify ASGI middleware for test stability
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

# Default test environment settings
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")  # Default to SQLite for tests
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("DISABLE_AUTORUN", "1")
os.environ.setdefault("DISABLE_RATINGS", "0")
os.environ.setdefault("FAST_DEBATE", "1")
os.environ.setdefault("SSE_BACKEND", "memory")
os.environ.setdefault("RL_MAX_CALLS", "1000")
os.environ.setdefault("AUTH_RL_MAX_CALLS", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_MAX_RUNS_PER_HOUR", "50")
os.environ.setdefault("DEFAULT_MAX_TOKENS_PER_DAY", "150000")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ.setdefault("ENV", "test")


from worker.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


@pytest.fixture(scope="session", params=["asyncio"])
def anyio_backend(request):
    """Limit anyio tests to asyncio backend since trio isn't available in CI."""
    return request.param


@pytest.fixture(scope="session")
def test_database_url():
    """
    Create a unique test database for the entire test session.
    
    This fixture:
    1. Generates a unique SQLite database URL
    2. Initializes the database with all tables
    3. Sets the DATABASE_URL environment variable
    4. Reloads settings to use the test database
    5. Resets the global engine to use the test database
    6. Seeds initial billing plans
    7. Cleans up the database file after all tests complete
    """
    from decimal import Decimal

    from billing.models import BillingPlan
    from config import settings
    from database import init_db, reset_engine
    from database_async import reset_async_engine
    from sqlmodel import Session, select

    from tests.utils import cleanup_test_database, init_test_database, make_test_database_url
    
    # Generate unique test database URL
    db_url = make_test_database_url("session")
    
    # Initialize the database schema
    init_test_database(db_url)
    
    # Set environment variable and reload settings
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    settings.reload()
    
    # Reset the global engine to use the test database
    reset_engine()
    reset_async_engine()
    
    # Initialize database (creates tables if needed)
    init_db()
    
    # Seed billing plans
    from database import engine
    with Session(engine) as session:
        existing = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
        if not existing:
            session.add(
                BillingPlan(
                    slug="free",
                    name="Free",
                    is_default_free=True,
                    limits={
                        "max_debates_per_month": 5, 
                        "exports_enabled": False,
                        "allowed_model_tiers": ["standard"]
                    },
                )
            )
            session.add(
                BillingPlan(
                    slug="pro",
                    name="Pro",
                    price_monthly=Decimal("29.00"),
                    currency="USD",
                    limits={
                        "max_debates_per_month": 100, 
                        "exports_enabled": True,
                        "allowed_model_tiers": ["standard", "advanced"]
                    },
                )
            )
            session.commit()
    
    yield db_url
    
    # Cleanup: restore original DATABASE_URL and clean up test database
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)
    
    settings.reload()
    reset_engine()
    cleanup_test_database(db_url)


@pytest.fixture(autouse=True)
def reset_global_state(request, test_database_url, seed_billing_plans):
    """
    Runs before every test:
    - Truncates all tables for clean state
    - Re-seeds billing plans
    - Clears provider health registry
    - Resets SSE backend
    
    This ensures complete isolation between tests even when application code
    creates its own database sessions.
    """
    from config import settings
    from database import reset_engine
    from database_async import reset_async_engine
    from sse_backend import reset_sse_backend_for_tests

    from tests.utils import reset_provider_health, truncate_all_tables

    # Force environment to test mode and clear production flags
    os.environ["ENV"] = "test"
    os.environ.pop("RENDER", None)
    
    # Force the shared settings/engine to the session database even if other tests mutated env.
    if settings.DATABASE_URL != test_database_url:
        os.environ["DATABASE_URL"] = test_database_url
        settings.reload()
        reset_engine()
        reset_async_engine()

    # Truncate all tables to ensure clean state before each test
    truncate_all_tables()
    # Defensive cleanup for rate-limit counters/quotas in case a test swaps metadata
    from database import engine
    from models import UsageCounter, UsageQuota
    from sqlalchemy import delete
    from sqlmodel import Session
    with Session(engine) as session:
        session.exec(delete(UsageCounter))
        session.exec(delete(UsageQuota))
        session.commit()

    # Re-seed billing plans after truncation
    seed_billing_plans()

    # Ensure test runs always have ratings enabled unless explicitly disabled in a test
    settings.DISABLE_RATINGS = False

    # Reset provider health (circuit breaker state)
    reset_provider_health()

    # Reset SSE backend (in-memory event channels)
    reset_sse_backend_for_tests()

    yield


@pytest.fixture(scope="session")
def seed_billing_plans(test_database_url):
    """
    Provide a callable to re-seed billing plans after table truncation.
    
    Args:
        test_database_url: Ensures database is initialized before this fixture
    """
    from decimal import Decimal

    from billing.models import BillingPlan
    from database import engine
    from sqlmodel import Session, select
    
    def _seed():
        with Session(engine) as session:
            existing = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
            if not existing:
                session.add(
                    BillingPlan(
                        slug="free",
                        name="Free",
                        is_default_free=True,
                        limits={
                            "max_debates_per_month": 5, 
                            "exports_enabled": False,
                            "allowed_model_tiers": ["standard"]
                        },
                    )
                )
                session.add(
                    BillingPlan(
                        slug="pro",
                        name="Pro",
                        price_monthly=Decimal("29.00"),
                        currency="USD",
                        limits={
                            "max_debates_per_month": 100, 
                            "exports_enabled": True,
                            "allowed_model_tiers": ["standard", "advanced"]
                        },
                    )
                )
                session.commit()
    
    # Return the function so it can be called after truncation
    return _seed


@pytest.fixture
def db_session(test_database_url):
    """
    Provide a database session for a test.
    
    Note: We no longer use transaction-based isolation because application code
    creates its own sessions. Instead, we truncate tables between tests.
    """
    from database import engine
    from sqlmodel import Session
    
    session = Session(engine)
    
    yield session
    
    session.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_routes():
    """
    Mount test-only routes to the FastAPI app for the duration of the test session.
    """
    from main import app

    from tests.fake_routes import test_router
    
    app.include_router(test_router)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    from sse_backend import get_sse_backend
    # Ensure app.state.sse_backend is set for deps.get_sse_backend dependency
    app.state.sse_backend = get_sse_backend()
    return TestClient(app)


@pytest.fixture
def authenticated_client(client, db_session):
    from auth import COOKIE_NAME, create_access_token, hash_password
    from models import User
    
    email = "normal@example.com"
    password = "password"
    user = User(email=email, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    
    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    client.cookies.set(COOKIE_NAME, access_token)
    return client
