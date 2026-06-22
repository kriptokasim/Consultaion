from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlmodel import Session

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "debate",
    "message",
    "score",
    "debate_stage_checkpoint",
    "debate_continuation",
    "billing_reconciliation_runs",
    "billing_reconciliation_discrepancies",
]

MODEL_CRITICAL_COLUMNS: dict[str, list[str]] = {
    "debate": ["id", "prompt", "status", "created_at", "updated_at", "user_id"],
    "message": ["id", "debate_id", "role", "content", "created_at"],
    "score": ["id", "debate_id", "persona", "score", "created_at"],
    "debate_continuation": [
        "id", "debate_id", "status", "created_at",
        "cancelled_at", "paused_at", "failure_code", "failure_detail_safe",
        "credit_reservation_id", "retry_of_continuation_id"
    ],
}


def ensure_alembic_version_table(session: Session) -> None:
    """Create the alembic_version table if it does not exist."""
    inspector = inspect(session.get_bind())
    if "alembic_version" not in inspector.get_table_names():
        logger.info("Creating alembic_version table")
        session.execute(
            text(
                "CREATE TABLE alembic_version ("
                "    version_num VARCHAR(128) NOT NULL"
                ")"
            )
        )
        session.commit()
        logger.info("alembic_version table created")


def widen_version_column(session: Session) -> bool:
    """Widen version_num to VARCHAR(128) on PostgreSQL if needed.

    Returns True if the column was widened, False otherwise.
    """
    dialect = session.get_bind().dialect.name
    if dialect != "postgresql":
        return False

    inspector = inspect(session.get_bind())
    columns = inspector.get_columns("alembic_version")
    version_col = next((c for c in columns if c["name"] == "version_num"), None)
    if not version_col:
        return False

    col_type = str(version_col.get("type", ""))
    if "VARCHAR" in col_type and "128" not in col_type:
        logger.warning(
            "Widening alembic_version.version_num from %s to VARCHAR(128)",
            col_type,
        )
        session.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(128)"
            )
        )
        session.commit()
        logger.info("Column widened successfully")
        return True

    return False


def get_current_revisions(session: Session) -> list[str]:
    """Return the current revision(s) stored in alembic_version."""
    try:
        result = session.execute(text("SELECT version_num FROM alembic_version"))
        return [row[0] for row in result]
    except Exception as exc:
        logger.warning("Failed to read current revision: %s", exc)
        return []


def get_migration_heads() -> list[str]:
    """Return the head revision(s) from the Alembic migration tree."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_heads()


def get_all_revisions() -> list[str]:
    """Return all revision IDs from the migration tree."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(alembic_cfg)
    return [r.revision for r in script.walk_revisions() if r.revision != "heads"]


def verify_required_tables(session: Session) -> list[str]:
    """Check that all required tables exist.

    Returns a list of missing table names.
    """
    inspector = inspect(session.get_bind())
    existing = set(inspector.get_table_names())
    missing = [t for t in REQUIRED_TABLES if t not in existing]
    return missing


def verify_critical_columns(session: Session) -> list[str]:
    """Check that model-critical columns exist on required tables.

    Returns a list of missing column references (table.column).
    """
    inspector = inspect(session.get_bind())
    missing = []
    for table, columns in MODEL_CRITICAL_COLUMNS.items():
        try:
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            for col in columns:
                if col not in existing_cols:
                    missing.append(f"{table}.{col}")
        except Exception:
            missing.append(f"{table}.*")
    return missing
