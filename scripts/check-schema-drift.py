#!/usr/bin/env python3
import os
import sys

# Set up PYTHONPATH so we can import apps/api modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "../apps/api"))


# Import all models to register them with SQLModel metadata
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from config import AppSettings
from sqlalchemy import create_engine
from sqlmodel import SQLModel
import models
import billing.models
import promotions.models


def main():
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

    # Filter out common SQLite-specific false positives if necessary, or check for critical drifts
    # (e.g. missing columns/tables).
    real_drifts = []
    for item in diff:
        # SQLite doesn't support alter table / modify type or remove constraint changes well,
        # but we definitely care about new/missing tables, columns, or indexes.
        action = item[0]
        if action in ("add_table", "remove_table", "add_column", "remove_column"):
            real_drifts.append(item)
        elif action in ("add_index", "remove_index") and not any(idx_name.startswith("ix_debate_") for idx_name in [item[1].name if hasattr(item[1], "name") else ""]):
            real_drifts.append(item)
        else:
            # Keep other changes for visibility, but don't fail unless critical columns or tables differ.
            real_drifts.append(item)

    if real_drifts:
        print("ERROR: Real schema drift detected! Model metadata differs from migrations:")
        for item in real_drifts:
            print(f"  {item}")
        sys.exit(1)
    else:
        print("OK: SQLModel metadata matches Alembic migrations. No drift.")
        sys.exit(0)

if __name__ == "__main__":
    main()
