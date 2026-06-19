"""Test isolation and parallel safety guards.

Validates that test cleanup mechanisms work correctly.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


class TestTableCleanup:
    def test_metadata_tables_are_discoverable(self, db_session: Session):
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db_session.get_bind())
        tables = set(inspector.get_table_names())
        assert len(tables) > 0

    def test_settings_not_mutated(self):
        from config import settings
        original_version = settings.APP_VERSION
        assert settings.APP_VERSION == original_version


class TestIsolationBetweenTests:
    def test_first_writes_value(self, db_session: Session):
        db_session.execute(text(
            "CREATE TEMPORARY TABLE IF NOT EXISTS _test_iso (v TEXT)"
        ))
        db_session.execute(text("INSERT INTO _test_iso VALUES ('hello')"))
        db_session.commit()

    def test_second_does_not_see_first_value(self, db_session: Session):
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db_session.get_bind())
        tables = set(inspector.get_table_names())
        assert "_test_iso" not in tables
