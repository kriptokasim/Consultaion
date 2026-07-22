"""Regression coverage for the cross-dialect P159 team dedup migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "p159_billing_team_integrity.py"
    )
    spec = importlib.util.spec_from_file_location("p159_billing_team_integrity", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p159_upgrade_runs_on_sqlite_and_preserves_duplicate_audit(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE debate (id VARCHAR PRIMARY KEY)"))
        connection.execute(sa.text(
            "CREATE TABLE team_member ("
            "id INTEGER PRIMARY KEY, team_id VARCHAR NOT NULL, "
            "user_id VARCHAR NOT NULL, role VARCHAR NOT NULL)"
        ))
        connection.execute(sa.text(
            "INSERT INTO team_member (id, team_id, user_id, role) VALUES "
            "(1, 'team-1', 'user-1', 'viewer'), "
            "(2, 'team-1', 'user-1', 'owner')"
        ))

        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()

        members = connection.execute(sa.text(
            "SELECT id, role FROM team_member ORDER BY id"
        )).all()
        audit = connection.execute(sa.text(
            "SELECT original_id, team_id, user_id, role "
            "FROM team_member_dedup_audit"
        )).all()

        assert members == [(1, "owner")]
        assert audit == [(2, "team-1", "user-1", "owner")]
        indexes = {
            item["name"] for item in sa.inspect(connection).get_indexes("team_member")
        }
        assert "uq_team_member_team_user" in indexes
