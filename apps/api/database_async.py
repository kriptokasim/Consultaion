from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings


def _engine_kwargs() -> dict:
    """Build async-engine kwargs without leaking test connections across event loops."""
    connect_args = {}
    if "sqlite" in settings.DATABASE_URL_ASYNC:
        connect_args["check_same_thread"] = False

    # Patchset: PgBouncer safety for async engine. Disable prepared statements
    # when using Supabase pooler (transaction mode) to avoid stale statements.
    if ":6543" in settings.DATABASE_URL_ASYNC or "pooler.supabase.com" in settings.DATABASE_URL_ASYNC:
        connect_args["prepare_threshold"] = None

    kwargs = {
        "echo": settings.DB_ECHO,
        "future": True,
        "connect_args": connect_args,
    }

    # Tests intentionally reset the global engine between cases while pytest-anyio
    # and pytest-asyncio may use different event-loop lifetimes. A pooled aiosqlite
    # connection can therefore remain bound to a loop that has already closed.
    # NullPool keeps production pooling unchanged while making each test checkout
    # use a fresh connection that belongs to the current loop.
    if settings.ENV == "test":
        kwargs["poolclass"] = NullPool

    return kwargs


async_engine = create_async_engine(settings.DATABASE_URL_ASYNC, **_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for background tasks."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def reset_async_engine():
    """Reset the global async engine to the current settings database URL.

    In test mode the replacement engine uses ``NullPool`` so a connection created
    under one pytest event loop cannot be reused after that loop is closed.
    """
    global async_engine, AsyncSessionLocal

    async_engine = create_async_engine(settings.DATABASE_URL_ASYNC, **_engine_kwargs())
    AsyncSessionLocal.configure(bind=async_engine)
