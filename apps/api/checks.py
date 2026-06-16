from __future__ import annotations

import logging
from typing import Any

from alembic import config as alembic_config, script
from alembic.runtime import migration
from database import engine
from sqlalchemy import text
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)


def _check_schema_integrity() -> dict[str, Any]:
    """Check required tables and columns exist."""
    from services.migration_safety import verify_required_tables, verify_critical_columns

    with engine.connect() as conn:
        from sqlmodel import Session
        session = Session(bind=conn)
        missing_tables = verify_required_tables(session)
        missing_cols = verify_critical_columns(session)

    return {
        "missing_tables": missing_tables,
        "missing_columns": missing_cols,
        "schema_ok": len(missing_tables) == 0 and len(missing_cols) == 0,
    }


def check_db_readiness() -> tuple[bool, dict[str, Any]]:
    """
    Ping DB, check migration status, and verify schema integrity.
    
    Returns:
        (ok, details_dict)
    """
    result = {"ok": False, "error": None}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["ping"] = True
        
        alembic_cfg = alembic_config.Config("alembic.ini")
        script_dir = script.ScriptDirectory.from_config(alembic_cfg)
        head = script_dir.get_current_head()
        
        with engine.connect() as conn:
            context = migration.MigrationContext.configure(conn)
            current = context.get_current_revision()
            
        result["revision"] = {"current": current, "head": head}
        
        schema = _check_schema_integrity()
        result["schema"] = schema
        
        if current != head and head is not None:
             result["error"] = f"Pending migrations: current={current}, head={head}"
             result["ok"] = False
        elif not schema["schema_ok"]:
             result["error"] = (
                 f"Schema integrity check failed: "
                 f"missing tables={schema['missing_tables']} "
                 f"missing columns={schema['missing_columns']}"
             )
             result["ok"] = False
        else:
             result["ok"] = True
            
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Readiness DB check failed: {e}")
        
    return result["ok"], result


async def check_sse_readiness() -> tuple[bool, dict[str, Any]]:
    """
    Check SSE backend connectivity.
    
    Returns:
        (ok, details_dict)
    """
    result = {"ok": False, "backend": "unknown"}
    try:
        backend = get_sse_backend()
        result["backend"] = type(backend).__name__
        
        # Ping returns bool
        is_ok = await backend.ping()
        result["ok"] = is_ok
        if not is_ok:
            result["error"] = "Backend ping failed"
            
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Readiness SSE check failed: {e}")
        
    return result["ok"], result
