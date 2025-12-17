from contextlib import asynccontextmanager
from typing import AsyncGenerator

from config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Check if using SQLite (for local) or Postgres
connect_args = {}
if "sqlite" in settings.DATABASE_URL_ASYNC:
    connect_args["check_same_thread"] = False

async_engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    echo=settings.DB_ECHO,
    future=True,  # Standard for 1.4/2.0
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
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
    """
    Reset the global async engine to use the current settings.DATABASE_URL_ASYNC.
    Used in tests to switch databases.
    """
    global async_engine, AsyncSessionLocal
    
    connect_args = {}
    if "sqlite" in settings.DATABASE_URL_ASYNC:
        connect_args["check_same_thread"] = False

    # Create new engine
    new_engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=settings.DB_ECHO,
        future=True,
        connect_args=connect_args,
    )
    
    # Update global
    async_engine = new_engine
    
    # Reconfigure factory
    AsyncSessionLocal.configure(bind=async_engine)
