import os
import contextlib
from typing import Dict, Optional, Generator
from uuid import uuid4
from pathlib import Path

from config import settings
from parliament.provider_health import reset_health_state, clear_all_health_states


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
    Generate a unique SQLite database URL for testing.
    
    Args:
        test_id: Optional identifier for the test database. If not provided,
                 a random UUID will be used.
    
    Returns:
        A SQLite database URL string
    """
    if test_id is None:
        test_id = uuid4().hex[:12]
    
    # Use /tmp for test databases to avoid cluttering the project directory
    db_path = Path(f"/tmp/consultaion_test_{test_id}.db")
    return f"sqlite:///{db_path}"


def init_test_database(database_url: str) -> None:
    """
    Initialize a test database with all required tables.
    
    This creates all tables using SQLModel.metadata.create_all(),
    which matches the pattern used in the application's init_db().
    
    Args:
        database_url: The database URL to initialize
    """
    from sqlmodel import create_engine, SQLModel
    
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
    from sqlmodel import SQLModel
    from database import engine
    
    # Get all table names from SQLModel metadata
    tables = SQLModel.metadata.sorted_tables
    
    # Use a connection to execute raw SQL
    with engine.begin() as connection:
        # For SQLite, we need to disable foreign key constraints temporarily
        if engine.url.get_backend_name() == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        
        # Truncate each table (in reverse order to handle dependencies)
        for table in reversed(tables):
            try:
                if engine.url.get_backend_name() == "sqlite":
                    # SQLite doesn't support TRUNCATE, use DELETE
                    connection.exec_driver_sql(f"DELETE FROM {table.name}")
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
                    connection.exec_driver_sql(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE")
            except Exception as e:
                # Log but don't fail - some tables might not exist or can't be truncated
                import sys
                print(f"Warning: Could not truncate table {table.name}: {e}", file=sys.stderr)
        
        # Re-enable foreign key constraints for SQLite
        if engine.url.get_backend_name() == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")

