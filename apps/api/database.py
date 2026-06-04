from contextlib import contextmanager

from config import settings
from sqlmodel import Session, SQLModel, create_engine


def _create_engine():
    database_url = settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    
    # Patchset 68.0: PgBouncer safety for psycopg3
    # Disable prepared statements when using Supabase pooler (transaction mode)
    # to avoid "prepared statement does not exist" errors
    if ":6543" in database_url or "pooler.supabase.com" in database_url:
        connect_args["prepare_threshold"] = None
    
    engine_kwargs = {
        "echo": settings.DB_ECHO,
        "connect_args": connect_args,
        "pool_pre_ping": True,
    }
    if not database_url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
            }
        )
    return create_engine(database_url, **engine_kwargs)


engine = _create_engine()


def init_db() -> None:
    backend = engine.url.get_backend_name()
    if backend == "sqlite" or settings.FORCE_CREATE_ALL:
        SQLModel.metadata.create_all(engine)
        
        # Safe dynamic column migrations for SQLite
        from sqlalchemy import text, inspect
        import logging
        db_logger = logging.getLogger("database")
        
        with engine.connect() as conn:
            inspector = inspect(engine)
            
            # 1. Alter debate table
            try:
                columns = [c["name"] for c in inspector.get_columns("debate")]
                if "gateway_policy" not in columns:
                    conn.execute(text("ALTER TABLE debate ADD COLUMN gateway_policy TEXT"))
                    conn.commit()
            except Exception as e:
                db_logger.warning("Failed to alter debate table: %s", e)
                
            # 2. Alter llm_usage_log table
            try:
                columns = [c["name"] for c in inspector.get_columns("llm_usage_log")]
                new_cols = {
                    "gateway": "TEXT",
                    "model_pool": "TEXT",
                    "routing_policy": "TEXT",
                    "fallback_used": "BOOLEAN DEFAULT 0",
                    "fallback_reason": "TEXT",
                    "user_plan": "TEXT",
                    "estimated_cost_usd": "FLOAT DEFAULT 0.0",
                    "retry_count": "INTEGER DEFAULT 0"
                }
                for col, col_type in new_cols.items():
                    if col not in columns:
                        conn.execute(text(f"ALTER TABLE llm_usage_log ADD COLUMN {col} {col_type}"))
                        conn.commit()
            except Exception as e:
                db_logger.warning("Failed to alter llm_usage_log table: %s", e)
                
            # 3. Alter user table for hosted credits
            try:
                columns = [c["name"] for c in inspector.get_columns("user")]
                new_user_cols = {
                    "hosted_credits_limit": "INTEGER DEFAULT 10",
                    "hosted_credits_used": "INTEGER DEFAULT 0",
                    "hosted_credit_source": "TEXT DEFAULT 'signup'"
                }
                for col, col_type in new_user_cols.items():
                    if col not in columns:
                        conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {col_type}"))
                        conn.commit()
            except Exception as e:
                db_logger.warning("Failed to alter user table: %s", e)



def get_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope():
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    global engine
    try:
        engine.dispose()
    except Exception:
        pass
    engine = _create_engine()
