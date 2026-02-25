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
