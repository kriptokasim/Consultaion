import contextlib
import os
import tempfile
from pathlib import Path
from typing import Dict, Generator, Optional
from uuid import uuid4

from parliament.provider_health import clear_all_health_states, reset_health_state

from config import settings


@contextlib.contextmanager
def override_env(vars: Dict[str, Optional[str]]) -> Generator[None, None, None]:
    """
    Context manager to temporarily override environment variables.
    
    Args:
        vars: Dictionary of env vars to set. If value is None, the var is unset.
    """
    original = {}
    
    # Save original values and apply overrides
    for key, value in vars.items():
        original[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
            
    try:
        yield
    finally:
        # Restore original values
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextlib.contextmanager
def settings_context(**overrides) -> Generator[None, None, None]:
    """
    Context manager to override settings via environment variables and reload.
    
    Usage:
        with settings_context(FAST_DEBATE="1", ENV="test"):
            assert settings.FAST_DEBATE is True
            
    Args:
        **overrides: Key-value pairs of settings to override.
    """
    # Convert all values to strings (or None) for env vars
    env_vars = {k: str(v) if v is not None else None for k, v in overrides.items()}
    
    with override_env(env_vars):
        settings.reload()
        try:
            yield
        finally:
            settings.reload()


def reset_provider_health(provider: Optional[str] = None, model: Optional[str] = None) -> None:
    """
    Reset provider health state.
    
    Args:
        provider: Optional provider name to reset specific state
        model: Optional model name to reset specific state
    """
    if provider and model:
        reset_health_state(provider, model)
    else:
        clear_all_health_states()


# ============================================================================
# Database Test Helpers
# ============================================================================

def make_test_database_url(test_id: Optional[str] = None) -> str:
    """
    Generate a unique SQLite database URL for testing, or use DATABASE_URL if configured for PostgreSQL.
    
    Args:
        test_id: Optional identifier for the test database. If not provided,
                 a random UUID will be used.
    
    Returns:
        A database URL string
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url.startswith("postgresql"):
        return env_url

    if test_id is None:
        test_id = uuid4().hex[:12]
    
    # Use the platform temp directory (works on Windows and POSIX).
    db_path = Path(tempfile.gettempdir()) / f"consultaion_test_{test_id}.db"
    return f"sqlite:///{db_path}"


def init_test_database(database_url: str) -> None:
    """
    Initialize a test database with all required tables.
    
    This creates all tables using SQLModel.metadata.create_all(),
    which matches the pattern used in the application's init_db().
    
    Args:
        database_url: The database URL to initialize
    """
    from sqlmodel import SQLModel, create_engine
    
    # Create engine for this specific database
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    test_engine = create_engine(database_url, connect_args=connect_args, echo=False)
    
    # Create all tables
    SQLModel.metadata.create_all(test_engine)
    
    # Dispose of the engine
    test_engine.dispose()


def cleanup_test_database(database_url: str) -> None:
    """
    Clean up a test database file.
    
    Args:
        database_url: The database URL to clean up
    """
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception:
            pass  # Ignore cleanup errors


def unique_email(prefix: str = "user") -> str:
    """
    Generate a unique email address for testing.
    
    Args:
        prefix: Prefix for the email address
    
    Returns:
        A unique email address
    """
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


def truncate_all_tables() -> None:
    """
    Truncate all tables in the test database to ensure clean state between tests.
    
    This is more reliable than transaction-based isolation when application code
    creates its own database sessions.
    """
    from database import engine
    from sqlalchemy import inspect
    from sqlmodel import SQLModel
    
    # Get all table names from SQLModel metadata
    tables = SQLModel.metadata.sorted_tables
    
    is_sqlite = engine.url.get_backend_name() == "sqlite"

    # SQLite ignores PRAGMA foreign_keys inside a transaction, so both toggles
    # must run between commits; otherwise the pooled connection goes back to
    # the pool with enforcement silently left off.
    with engine.connect() as connection:
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
            connection.commit()
        existing_tables = set(inspect(connection).get_table_names())

        # Truncate each table (in reverse order to handle dependencies)
        for table in reversed(tables):
            if table.name not in existing_tables:
                continue
            table_identifier = connection.dialect.identifier_preparer.format_table(table)
            try:
                if engine.url.get_backend_name() == "sqlite":
                    # SQLite doesn't support TRUNCATE, use DELETE
                    connection.exec_driver_sql(f"DELETE FROM {table_identifier}")
                    # Reset the auto-increment counter for SQLite (if it exists)
                    # sqlite_sequence only exists if there are tables with AUTOINCREMENT
                    try:
                        connection.exec_driver_sql(
                            f"DELETE FROM sqlite_sequence WHERE name='{table.name}'"
                        )
                    except Exception:
                        # sqlite_sequence might not exist yet, that's OK
                        pass
                else:
                    # PostgreSQL and others support TRUNCATE
                    connection.exec_driver_sql(
                        f"TRUNCATE TABLE {table_identifier} RESTART IDENTITY CASCADE"
                    )
            except Exception as e:
                # Log but don't fail - some tables might not exist or can't be truncated
                import sys
                print(f"Warning: Could not truncate table {table.name}: {e}", file=sys.stderr)

        connection.commit()
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.commit()
            enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            assert enabled == 1, "truncate_all_tables left SQLite FK enforcement off"



def ensure_user(session, user_id: str, **fields):
    """Create the user row a fixture references by id, if it is missing.

    Foreign keys are enforced in tests, so a row that names a user must point
    at a real one.
    """
    from models import User

    user = session.get(User, user_id)
    if user is None:
        fields.setdefault("email", f"{user_id}@fixtures.consultaion.test")
        fields.setdefault("password_hash", "not-a-real-hash")
        user = User(id=user_id, **fields)
        session.add(user)
        session.flush()
    return user


def ensure_debate(session, debate_id: str, *, user_id: Optional[str] = None, **fields):
    """Create the debate row a fixture references by id, if it is missing."""
    from models import Debate

    debate = session.get(Debate, debate_id)
    if debate is None:
        if user_id is not None:
            ensure_user(session, user_id)
        fields.setdefault("prompt", "fixture debate")
        fields.setdefault("status", "queued")
        debate = Debate(id=debate_id, user_id=user_id, **fields)
        session.add(debate)
        session.flush()
    return debate


def add_rows_in_order(session, *rows) -> None:
    """Insert rows in the order given, flushing after each.

    Without a relationship() between two models the ORM does not order their
    INSERTs by foreign key, so a single add_all() can insert a child first.
    """
    for row in rows:
        session.add(row)
        session.flush()


def seed_debate(debate_id: str, *, user_id: Optional[str] = None, **fields) -> str:
    """Commit a debate row (and its user) for tests that only know its id."""
    from database import session_scope

    with session_scope() as session:
        ensure_debate(session, debate_id, user_id=user_id, **fields)
    return debate_id
