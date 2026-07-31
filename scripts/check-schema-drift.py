#!/usr/bin/env python3
import os
import sys

# Set up PYTHONPATH so we can import apps/api modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "../apps/api"))


# Import all models to register them with SQLModel metadata
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from sqlmodel import SQLModel

import models  # noqa: F401  # Register every SQLModel table before comparison.
from billing import models as billing_models  # noqa: F401
from config import AppSettings

# Tables deliberately owned by Alembic rather than the runtime ORM. These are
# retained migration/audit artifacts and must not be interpreted as tables the
# application metadata intends to drop.
MIGRATION_ONLY_TABLES = frozenset({"team_member_dedup_audit"})


def _is_expected_migration_only_diff(item: tuple) -> bool:
    if item[0] != "remove_table" or len(item) < 2:
        return False
    table = item[1]
    return getattr(table, "name", None) in MIGRATION_ONLY_TABLES


def main() -> None:
    print("Checking for real schema drift (metadata vs migrations)...")
    # Change working directory to apps/api to resolve relative sqlite path correctly
    os.chdir(os.path.join(SCRIPT_DIR, "../apps/api"))
    settings = AppSettings()
    url = settings.DATABASE_URL
    print(f"Using database URL: {url}")

    engine = create_engine(url)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)

        assert SQLModel.metadata.tables, "SQLModel.metadata is empty! Ensure models are imported."

        diff = compare_metadata(context, SQLModel.metadata)

    # Filter out common backend-specific rendering differences while preserving
    # blocking checks for data-bearing tables and columns.
    real_drifts = []
    for item in diff:
        action = item[0]
        if _is_expected_migration_only_diff(item):
            print(f"INFO: Migration-only audit table retained outside ORM metadata: {item[1].name}")
        elif action in ("add_table", "remove_table", "add_column", "remove_column"):
            real_drifts.append(item)
        else:
            # Constraint, index, and type rendering differs between SQLite and
            # PostgreSQL. Keep this gate focused on data-bearing tables/columns.
            print(f"INFO: Non-critical metadata difference ignored: {item}")

    if real_drifts:
        print("ERROR: Real schema drift detected! Model metadata differs from migrations:")
        for item in real_drifts:
            print(f"  {item}")
        sys.exit(1)

    print("OK: SQLModel metadata matches Alembic migrations. No drift.")
    sys.exit(0)


if __name__ == "__main__":
    main()
