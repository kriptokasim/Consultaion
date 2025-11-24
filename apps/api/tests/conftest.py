import pytest
import os

# Simplify ASGI middleware for test stability
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

# Default test environment settings
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")  # Default to SQLite for tests
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("DISABLE_AUTORUN", "1")
os.environ.setdefault("DISABLE_RATINGS", "1")
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
    from tests.utils import make_test_database_url, init_test_database, cleanup_test_database
    from config import settings
    from database import reset_engine, init_db
    from sqlmodel import Session, select
    from billing.models import BillingPlan
    from decimal import Decimal
    
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
                    limits={"max_debates_per_month": 5, "exports_enabled": True},
                )
            )
            session.add(
                BillingPlan(
                    slug="pro",
                    name="Pro",
                    price_monthly=Decimal("29.00"),
                    currency="USD",
                    limits={"max_debates_per_month": 100, "exports_enabled": True},
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
    
    This ensures complete isolation between tests even when application code
    creates its own database sessions.
    """
    from tests.utils import reset_provider_health, truncate_all_tables
    
    # Truncate all tables to ensure clean state
    # (Skip for the first test in the session to avoid truncating seed data)
    if not hasattr(reset_global_state, '_first_run'):
        reset_global_state._first_run = True
    else:
        truncate_all_tables()
        # Re-seed billing plans after truncation
        seed_billing_plans()

    # Reset provider health (circuit breaker state)
    reset_provider_health()

    yield


@pytest.fixture(scope="session")
def seed_billing_plans(test_database_url):
    """
    Provide a callable to re-seed billing plans after table truncation.
    
    Args:
        test_database_url: Ensures database is initialized before this fixture
    """
    from sqlmodel import Session, select
    from database import engine
    from billing.models import BillingPlan
    from decimal import Decimal
    
    def _seed():
        with Session(engine) as session:
            existing = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
            if not existing:
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
                        price_monthly=Decimal("29.00"),
                        currency="USD",
                        limits={"max_debates_per_month": 100, "exports_enabled": True},
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
    from sqlmodel import Session
    from database import engine
    
    session = Session(engine)
    
    yield session
    
    session.close()

