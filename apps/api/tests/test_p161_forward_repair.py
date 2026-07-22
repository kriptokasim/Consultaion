"""Forward migration coverage for RLS and hosted-credit drift repair."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "p161_security_billing.py"
    )
    spec = importlib.util.spec_from_file_location(
        "p161_security_billing", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Inspector:
    def get_table_names(self):
        return ["usage_ledger_entry", "debate", "debate_continuation"]

    def get_columns(self, table_name):
        if table_name != "usage_ledger_entry":
            return []
        return [
            {"name": name}
            for name in (
                "id",
                "kind",
                "status",
                "debate_id",
                "meta",
                "settled_at",
                "refunded_at",
            )
        ]


def test_p161_postgres_repairs_only_policyless_rls_and_quarantines_unknowns(
    monkeypatch,
):
    migration = _load_migration()
    statements = []

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", _Bind)
    monkeypatch.setattr(migration.op, "execute", statements.append)
    monkeypatch.setattr(migration, "inspect", lambda _bind: _Inspector())

    migration.upgrade()

    rendered = "\n".join(str(statement) for statement in statements)
    assert "DISABLE ROW LEVEL SECURITY" in rendered
    assert "NOT EXISTS" in rendered
    assert "pg_policy" in rendered
    assert "c.relname IN" in rendered
    assert "'debate'" in rendered
    assert "'usage_ledger_entry'" in rendered
    assert "unmanaged_default_deny_table" not in migration.P160_MANAGED_PUBLIC_TABLES
    assert "unmanaged_default_deny_table" not in rendered
    assert "reconciliation_pending" in rendered
    assert "credit_reservation_id = ule.id" in rendered
    assert "continuation_id" in rendered
    assert "ENABLE ROW LEVEL SECURITY" not in rendered


def test_p161_sqlite_is_safe_noop(monkeypatch):
    migration = _load_migration()
    statements = []

    class _Dialect:
        name = "sqlite"

    class _Bind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", _Bind)
    monkeypatch.setattr(migration.op, "execute", statements.append)
    monkeypatch.setattr(migration, "inspect", lambda _bind: _Inspector())

    migration.upgrade()

    assert statements == []
