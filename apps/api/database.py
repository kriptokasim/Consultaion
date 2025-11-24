from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from config import settings

def _create_engine():
    database_url = settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
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
            }
        )
    return create_engine(database_url, **engine_kwargs)


engine = _create_engine()


def init_db() -> None:
    backend = engine.url.get_backend_name()
    if backend == "sqlite" or settings.FORCE_CREATE_ALL:
        SQLModel.metadata.create_all(engine)


def get_session():
    try:  # pragma: no cover - debug aid
        with open("/tmp/auth_debug.log", "a", encoding="utf-8") as fp:
            fp.write(f"get_session start url={getattr(engine, 'url', None)}\n")
    except Exception:
        pass
    with Session(engine) as session:
        try:
            yield session
            try:
                with open("/tmp/auth_debug.log", "a", encoding="utf-8") as fp:
                    fp.write("get_session after_yield\n")
            except Exception:
                pass
        finally:
            try:
                with open("/tmp/auth_debug.log", "a", encoding="utf-8") as fp:
                    fp.write("get_session exit\n")
            except Exception:
                pass


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
    try:  # pragma: no cover - debug
        from pathlib import Path
        with open("/tmp/settings_debug.log", "a", encoding="utf-8") as fp:
            fp.write(f"reset_engine to {settings.DATABASE_URL}\n")
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass
    engine = _create_engine()
