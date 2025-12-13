import os

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from billing.models import BillingPlan, BillingSubscription, BillingUsage  # noqa: F401
from config import settings
from dotenv import load_dotenv
from models import (  # noqa: F401
    APIKey,
    AuditLog,
    Debate,
    DebateRound,
    Message,
    PairwiseVote,
    RatingPersona,
    Score,
    Team,
    TeamMember,
    UsageCounter,
    UsageQuota,
    User,
    Vote,
)
from promotions.models import Promotion  # noqa: F401
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Patchset 68.0: Prefer DATABASE_URL_MIGRATIONS for direct Supabase connection
# This allows migrations to bypass PgBouncer (port 5432 direct vs 6543 pooler)
DATABASE_URL_MIGRATIONS = os.getenv("DATABASE_URL_MIGRATIONS")
DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL_MIGRATIONS:
    # Use direct connection for migrations
    url = DATABASE_URL_MIGRATIONS.replace('%', '%%')
else:
    # Fallback to runtime URL (escape % chars for configparser)
    url = DATABASE_URL.replace('%', '%%')

if not url:
    raise RuntimeError("DATABASE_URL is not set")

config.set_main_option("sqlalchemy.url", url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # Patchset 68.1: PgBouncer safety for Alembic
    # If using pooler (port 6543), disable prepared statements
    connect_args = {}
    url_str = config.get_main_option("sqlalchemy.url") or ""
    if ":6543" in url_str or "pooler.supabase.com" in url_str:
        connect_args["prepare_threshold"] = 0

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
