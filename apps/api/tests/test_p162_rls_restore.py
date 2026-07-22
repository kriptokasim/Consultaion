"""Regression coverage for the P162 applied-P161 RLS repair."""

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
        / "p162_restore_unmanaged_rls.py"
    )
    spec = importlib.util.spec_from_file_location(
        "p162_restore_unmanaged_rls", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ScalarResult:
    def __init__(self, *, values=(), scalar=None):
        self._values = list(values)
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._values

    def scalar_one_or_none(self):
        return self._scalar


class _Bind:
    dialect = postgresql.dialect()

    def __init__(self, states, policyless=()):
        self.states = dict(states)
        self.policyless = tuple(policyless)
        self.statements = []

    def execute(self, statement, params=None):
        rendered = str(statement)
        self.statements.append((rendered, params))
        if rendered.startswith("SELECT c.relname"):
            return _ScalarResult(values=self.policyless)
        if rendered.startswith("SELECT c.relrowsecurity"):
            return _ScalarResult(scalar=self.states.get(params["table_name"]))
        if rendered.startswith("ALTER TABLE"):
            table_name = rendered.rsplit(".", 1)[1].split()[0].strip('"')
            self.states[table_name] = True
            return _ScalarResult()
        raise AssertionError(f"Unexpected SQL: {rendered}")


def test_p162_is_a_forward_revision_from_applied_p161():
    migration = _load_migration()

    assert migration.down_revision == "p161_security_billing"
    assert migration.revision == "p162_restore_unmanaged_rls"


def test_p162_blocks_ambiguous_applied_p161_state_without_review(monkeypatch):
    migration = _load_migration()
    bind = _Bind(
        {"external_default_deny": False},
        policyless=("external_default_deny",),
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.delenv(migration.RLS_REVIEWED_ENV, raising=False)
    monkeypatch.delenv(migration.RLS_RESTORE_TABLES_ENV, raising=False)

    with pytest.raises(RuntimeError, match="cannot infer the pre-P161 RLS state"):
        migration.upgrade()

    assert bind.states["external_default_deny"] is False


def test_p162_restores_only_explicitly_reviewed_inventory(monkeypatch):
    migration = _load_migration()
    bind = _Bind(
        {
            "external_default_deny": False,
            "external_intentionally_open": False,
        },
        policyless=("external_default_deny", "external_intentionally_open"),
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setenv(migration.RLS_REVIEWED_ENV, "1")
    monkeypatch.setenv(
        migration.RLS_RESTORE_TABLES_ENV,
        "public.external_default_deny",
    )

    migration.upgrade()

    assert bind.states["external_default_deny"] is True
    assert bind.states["external_intentionally_open"] is False
    alter_statements = [sql for sql, _ in bind.statements if sql.startswith("ALTER TABLE")]
    assert alter_statements == [
        'ALTER TABLE public."external_default_deny" ENABLE ROW LEVEL SECURITY'
    ]


def test_p162_rejects_unknown_or_managed_restore_targets(monkeypatch):
    migration = _load_migration()
    bind = _Bind({"external_table": False}, policyless=("external_table",))
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setenv(migration.RLS_REVIEWED_ENV, "1")

    monkeypatch.setenv(migration.RLS_RESTORE_TABLES_ENV, "missing_table")
    with pytest.raises(RuntimeError, match="does not exist"):
        migration.upgrade()

    monkeypatch.setenv(migration.RLS_RESTORE_TABLES_ENV, "debate")
    with pytest.raises(RuntimeError, match="Consultaion-managed"):
        migration.upgrade()


def test_p162_is_a_safe_noop_on_sqlite(monkeypatch):
    migration = _load_migration()

    class _Dialect:
        name = "sqlite"

    class _SQLiteBind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _SQLiteBind())
    migration.upgrade()
