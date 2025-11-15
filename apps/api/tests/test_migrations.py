import os
from pathlib import Path
import subprocess

from sqlmodel import Session, create_engine, text

BASE_DIR = Path(__file__).resolve().parents[1]
SQLITE_PATH = BASE_DIR / "ci_migrate.db"
DB_URL = f"sqlite:///{SQLITE_PATH}"


def _run_alembic(database_url: str):
  env = os.environ.copy()
  env["DATABASE_URL"] = database_url
  subprocess.check_call(["alembic", "upgrade", "head"], cwd=BASE_DIR, env=env)


def test_000_sqlite_migration(tmp_path=None):
  if SQLITE_PATH.exists():
    SQLITE_PATH.unlink()
  _run_alembic(DB_URL)


def test_001_tables_exist_after_migration():
  engine = create_engine(DB_URL)
  with Session(engine) as session:
    session.exec(text("SELECT 1"))
    session.exec(text("SELECT 1 FROM pairwise_vote LIMIT 1"))
    session.exec(text("SELECT 1 FROM rating_persona LIMIT 1"))
