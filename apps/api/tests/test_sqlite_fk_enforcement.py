import database
import database_async
import pytest
from models import AuditLog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from tests.utils import truncate_all_tables


def _sync_fk_flag() -> int:
    with database.engine.connect() as conn:
        return conn.exec_driver_sql("PRAGMA foreign_keys").scalar()


def test_shared_engine_enforces_foreign_keys():
    assert _sync_fk_flag() == 1


def test_truncation_leaves_enforcement_on_for_pooled_connections():
    truncate_all_tables()
    truncate_all_tables()
    assert _sync_fk_flag() == 1


def test_orphan_audit_row_is_rejected():
    with Session(database.engine) as session:
        session.add(AuditLog(user_id="no-such-user", action="probe"))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.anyio
async def test_async_engine_enforces_foreign_keys():
    async with database_async.async_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1
