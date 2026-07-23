"""Regression coverage for upgrading an already-applied P162 database."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "p163_recheck_unmanaged_rls.py"
    )
    spec = importlib.util.spec_from_file_location("p163_recheck_unmanaged_rls", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, *, values=(), scalar=None):
        self._values = list(values)
        self._scalar = scalar

    def all(self):
        return self._values

    def scalar_one_or_none(self):
        return self._scalar


class _Bind:
    dialect = postgresql.dialect()

    def __init__(self, states, candidates=()):
        self.states = dict(states)
        self.candidates = tuple(candidates)
        self.statements = []

    def execute(self, statement, params=None):
        rendered = str(statement)
        self.statements.append((rendered, params))
        if rendered.startswith("SELECT c.relname"):
            return _Result(values=self.candidates)
        if rendered.startswith("SELECT c.relrowsecurity"):
            return _Result(scalar=self.states.get(params["table_name"]))
        if rendered.startswith("ALTER TABLE"):
            table_name = rendered.rsplit(".", 1)[1].split()[0].strip('"')
            self.states[table_name] = True
            return _Result()
        raise AssertionError(f"Unexpected SQL: {rendered}")


def test_p163_is_a_forward_revision_from_applied_p162():
    migration = _load_migration()

    assert migration.down_revision == "p162_restore_unmanaged_rls"
    assert migration.revision == "p163_recheck_unmanaged_rls"


def test_p163_rechecks_policy_bearing_disabled_table_after_p162(monkeypatch):
    migration = _load_migration()
    bind = _Bind(
        {"external_policy_added_after_p162": False},
        candidates=(("external_policy_added_after_p162", True),),
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.delenv(migration.RLS_REVIEWED_ENV, raising=False)
    monkeypatch.delenv(migration.RLS_RESTORE_TABLES_ENV, raising=False)

    with pytest.raises(
        RuntimeError,
        match=r"external_policy_added_after_p162 \(policies present\)",
    ):
        migration.upgrade()

    candidate_query = next(sql for sql, _ in bind.statements if sql.startswith("SELECT c.relname"))
    assert "EXISTS (" in candidate_query
    assert "AND NOT EXISTS" not in candidate_query
    assert bind.states["external_policy_added_after_p162"] is False


def test_p163_restores_reviewed_table_after_p162(monkeypatch):
    migration = _load_migration()
    bind = _Bind(
        {"external_policy_added_after_p162": False},
        candidates=(("external_policy_added_after_p162", True),),
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setenv(migration.RLS_REVIEWED_ENV, "1")
    monkeypatch.setenv(
        migration.RLS_RESTORE_TABLES_ENV,
        "public.external_policy_added_after_p162",
    )

    migration.upgrade()

    assert bind.states["external_policy_added_after_p162"] is True
    assert any(sql.startswith("ALTER TABLE public.") for sql, _ in bind.statements)


def test_p163_is_a_safe_noop_on_sqlite(monkeypatch):
    migration = _load_migration()

    class _Dialect:
        name = "sqlite"

    class _SQLiteBind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _SQLiteBind())
    migration.upgrade()
