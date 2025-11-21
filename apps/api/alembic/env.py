from logging.config import fileConfig
from pathlib import Path
import os

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from billing.models import BillingPlan, BillingSubscription, BillingUsage  # noqa: F401
from models import User, APIKey, Debate, DebateRound, Message, Score, PairwiseVote, RatingPersona  # noqa: F401
from promotions.models import Promotion  # noqa: F401

from dotenv import load_dotenv
from config import settings

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# allow DATABASE_URL env override when running migrations
url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
config.set_main_option("sqlalchemy.url", url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
