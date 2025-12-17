from __future__ import annotations

import logging
from typing import Any

from alembic import config as alembic_config, script
from alembic.runtime import migration
from database import engine
from sqlalchemy import text
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)


def check_db_readiness() -> tuple[bool, dict[str, Any]]:
    """
    Ping DB and check migration status.
    
    Returns:
        (ok, details_dict)
    """
    result = {"ok": False, "error": None}
    try:
        # 1. Ping (timeboxed by engine pool_timeout usually, but explicit connect advisable)
        # Using a fresh connection from the engine/pool
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["ping"] = True
        
        # 2. Migrations
        # Load Alembic config (assumes alembic.ini is in CWD or discoverable)
        alembic_cfg = alembic_config.Config("alembic.ini")
        script_dir = script.ScriptDirectory.from_config(alembic_cfg)
        head = script_dir.get_current_head()
        
        with engine.connect() as conn:
            context = migration.MigrationContext.configure(conn)
            current = context.get_current_revision()
            
        result["revision"] = {"current": current, "head": head}
        
        # We consider it NOT ready if migrations are pending
        if current != head and head is not None:
             result["error"] = f"Pending migrations: current={current}, head={head}"
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
