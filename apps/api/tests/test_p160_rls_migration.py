from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "p160_enable_public_rls.py"
    )
    spec = importlib.util.spec_from_file_location("p160_enable_public_rls", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p160_downgrade_does_not_disable_existing_rls(monkeypatch) -> None:
    migration = _load_migration()
    statements: list[object] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    assert statements == []


def test_p160_upgrade_does_not_enable_blanket_rls(monkeypatch) -> None:
    """P160 must NOT blanket-enable RLS on public tables.

    The deployment model is backend-only trusted: FastAPI handles auth.
    Enabling RLS without per-table policies would lock out the backend
    service account and break production.
    """
    migration = _load_migration()
    statements: list[object] = []

    class _Dialect:
        name = "postgresql"

    class _Inspector:
        def get_table_names(self, *_args, **_kwargs):
            return []

        def get_columns(self, *_args, **_kwargs):
            return []

        def get_indexes(self, *_args, **_kwargs):
            return []

    class _Bind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", _Bind)
    monkeypatch.setattr(migration.op, "execute", statements.append)
    monkeypatch.setattr(migration, "inspect", lambda *_args, **_kwargs: _Inspector())

    # Monkeypatch idempotent DDL ops so they don't actually try to create tables/indexes.
    monkeypatch.setattr(migration.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "alter_column", lambda *args, **kwargs: None)

    # The migration must not contain any RLS-enabling helper at all.
    assert not hasattr(migration, "_enable_public_table_rls"), (
        "P160 must not define _enable_public_table_rls"
    )

    # Running upgrade should not emit any ALTER TABLE ... ENABLE RLS.
    migration.upgrade()

    rendered = "\n".join(str(statement) for statement in statements)
    assert "ENABLE ROW LEVEL SECURITY" not in rendered
    assert "DISABLE ROW LEVEL SECURITY" not in rendered


def test_p160_keeps_billing_repairs() -> None:
    """The migration must still create billing_webhook_events and repair
    usage_ledger_entry settlement fields."""
    migration = _load_migration()

    assert hasattr(migration, "_ensure_billing_webhook_events")
    assert hasattr(migration, "_complete_usage_ledger_state")
