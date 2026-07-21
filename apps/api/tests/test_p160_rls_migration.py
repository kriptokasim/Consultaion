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


def test_p160_upgrade_only_enables_rls(monkeypatch) -> None:
    migration = _load_migration()
    statements: list[object] = []

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    monkeypatch.setattr(migration.op, "get_bind", _Bind)
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration._enable_public_table_rls()

    rendered = "\n".join(str(statement) for statement in statements)
    assert "ENABLE ROW LEVEL SECURITY" in rendered
    assert "DISABLE ROW LEVEL SECURITY" not in rendered
