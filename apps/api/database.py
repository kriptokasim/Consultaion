from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from config import settings

DATABASE_URL = settings.DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs = {
    "echo": settings.DB_ECHO,
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }
    )

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)


def init_db() -> None:
    backend = engine.url.get_backend_name()
    if backend == "sqlite" or settings.FORCE_CREATE_ALL:
        SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


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
