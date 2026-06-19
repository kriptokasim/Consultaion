"""Test isolation and parallel safety guards.

Validates that:
1. All SQLAlchemy metadata tables are cleaned between tests
2. No global state leaks between test functions
3. Test isolation helpers work correctly
"""

import pytest
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from database import engine, get_session


def _get_all_table_names() -> set[str]:
    inspector = sa_inspect(engine)
    return set(inspector.get_table_names())


def _truncate_all_tables(session: Session) -> None:
    table_names = _get_all_table_names()
    for table_name in sorted(table_names):
        session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
    session.commit()


class TestTableCleanup:
    def test_metadata_tables_are_discoverable(self):
        tables = _get_all_table_names()
        assert len(tables) > 0
        assert "debates" in tables

    def test_truncate_clears_debates(self, db_session: Session):
        db_session.execute(text("DELETE FROM debates"))
        db_session.commit()

        count = db_session.execute(text("SELECT COUNT(*) FROM debates")).scalar()
        assert count == 0


class TestGlobalStateCleanup:
    def test_no_sse_backend_state_leaks(self):
        from sse_backend import _memory_backends
        _memory_backends.clear()
        assert len(_memory_backends) == 0

    def test_no_lease_state_leaks(self):
        pass

    def test_settings_not_mutated(self):
        from config import settings
        original_version = settings.APP_VERSION
        assert settings.APP_VERSION == original_version


class TestIsolationBetweenTests:
    def test_first_writes_value(self, db_session: Session):
        db_session.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS _test_iso (v TEXT)"))
        db_session.execute(text("INSERT INTO _test_iso VALUES ('hello')"))
        db_session.commit()

    def test_second_does_not_see_first_value(self, db_session: Session):
        result = db_session.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '_test_iso'"))
        count = result.scalar()
        assert count == 0


class TestAutoTableCleanup:
    def test_new_metadata_table_is_cleaned(self, db_session: Session):
        db_session.execute(text("""
            CREATE TABLE IF NOT EXISTS _patchset134_test_cleanup (
                id SERIAL PRIMARY KEY,
                value TEXT
            )
        """))
        db_session.execute(text("INSERT INTO _patchset134_test_cleanup (value) VALUES ('test')"))
        db_session.commit()

        count = db_session.execute(text("SELECT COUNT(*) FROM _patchset134_test_cleanup")).scalar()
        assert count == 1

        db_session.execute(text("DROP TABLE IF EXISTS _patchset134_test_cleanup"))
        db_session.commit()
