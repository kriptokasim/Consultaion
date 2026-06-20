import os
import subprocess
from pathlib import Path

from sqlmodel import Session, create_engine, text

BASE_DIR = Path(__file__).resolve().parents[1]
DB_URL = os.environ.get("DATABASE_URL")

import sys

import pytest


def _run_alembic(database_url: str):
  env = os.environ.copy()
  env["DATABASE_URL"] = database_url
  env["JWT_SECRET"] = "dummy-secret-for-migrations"
  env["WEB_APP_ORIGIN"] = "http://localhost:3000"
  subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BASE_DIR, env=env)


def test_000_postgres_migration(tmp_path=None):
  if not DB_URL or "postgresql" not in DB_URL.lower():
      pytest.skip("Migration tests require PostgreSQL")
  _run_alembic(DB_URL)


def test_001_tables_exist_after_migration():
  if not DB_URL or "postgresql" not in DB_URL.lower():
      pytest.skip("Migration tests require PostgreSQL")
  engine = create_engine(DB_URL)
  with Session(engine) as session:
    session.exec(text("SELECT 1"))
    session.exec(text("SELECT 1 FROM pairwise_vote LIMIT 1"))
    session.exec(text("SELECT 1 FROM rating_persona LIMIT 1"))


def test_002_continuation_tables_exist():
  """Verify debate_continuation and debate_stage_checkpoint exist after migration."""
  if not DB_URL or "postgresql" not in DB_URL.lower():
      pytest.skip("Migration tests require PostgreSQL")
  engine = create_engine(DB_URL)
  with Session(engine) as session:
    session.exec(text("SELECT 1 FROM debate_continuation LIMIT 1"))
    session.exec(text("SELECT 1 FROM debate_stage_checkpoint LIMIT 1"))


def test_003_billing_tables_exist():
  """Verify billing-related tables exist after migration."""
  if not DB_URL or "postgresql" not in DB_URL.lower():
      pytest.skip("Migration tests require PostgreSQL")
  engine = create_engine(DB_URL)
  with Session(engine) as session:
    result = session.exec(text(
      "SELECT table_name FROM information_schema.tables "
      "WHERE table_schema = 'public' AND table_name LIKE 'billing%'"
    ))
    tables = {row[0] for row in result.all()}
    # At minimum these should exist
    expected = {"billing_plan", "billing_subscription", "billing_usage"}
    missing = expected - tables
    assert not missing, f"Missing billing tables: {missing}"


def test_004_alembic_current_matches_head():
  """Verify Alembic current matches head (no pending migrations)."""
  if not DB_URL or "postgresql" not in DB_URL.lower():
      pytest.skip("Migration tests require PostgreSQL")
  env = os.environ.copy()
  env["DATABASE_URL"] = DB_URL
  env["JWT_SECRET"] = "dummy-secret-for-migrations"
  env["WEB_APP_ORIGIN"] = "http://localhost:3000"

  current_out = subprocess.check_output(
    [sys.executable, "-m", "alembic", "current"],
    cwd=BASE_DIR, env=env, text=True
  ).strip()
  heads_out = subprocess.check_output(
    [sys.executable, "-m", "alembic", "heads"],
    cwd=BASE_DIR, env=env, text=True
  ).strip()

  # Extract revision hashes (first 12 chars of each line)
  current_rev = current_out.split()[0] if current_out else ""
  head_revs = [line.split()[0] for line in heads_out.splitlines() if line.strip()]

  assert len(head_revs) == 1, f"Expected 1 head, got {len(head_revs)}: {head_revs}"
  assert current_rev == head_revs[0], (
    f"Database at {current_rev} but migrations at {head_revs[0]}. Run 'alembic upgrade head'."
  )
