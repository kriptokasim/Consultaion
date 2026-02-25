import os
import subprocess
from pathlib import Path

from sqlmodel import Session, create_engine, text

BASE_DIR = Path(__file__).resolve().parents[1]
DB_URL = os.environ.get("DATABASE_URL")

import pytest
import sys


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
