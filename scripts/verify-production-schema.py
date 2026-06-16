#!/usr/bin/env python3
"""
Production schema verification — run before deploying or after migration.

Verifies:
1. Database is reachable
2. Alembic current revision equals head
3. At least one head exists
4. Required tables exist
5. Critical columns exist on required tables

Usage:
    python scripts/verify-production-schema.py
    python scripts/verify-production-schema.py --url <database-url>
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify production schema")
    parser.add_argument("--url", type=str, default=None)
    args = parser.parse_args()

    if args.url:
        database_url = args.url
    else:
        from config import settings
        database_url = settings.DATABASE_URL

    if not database_url:
        print("ERROR: DATABASE_URL is not set")
        sys.exit(1)

    from sqlalchemy import create_engine

    engine = create_engine(database_url, pool_pre_ping=True)

    from services.migration_safety import (
        get_current_revisions,
        get_migration_heads,
        verify_required_tables,
        verify_critical_columns,
    )

    from sqlmodel import Session

    errors: list[str] = []

    with Session(engine) as session:
        current = get_current_revisions(session)
        heads = get_migration_heads()

        if not current:
            errors.append("No current revision found")
        else:
            print(f"Current revision: {current[0]}")

        if not heads:
            errors.append("No migration head found")
        else:
            print(f"Expected head: {heads[0]}")
            if current and current[0] != heads[0]:
                errors.append(
                    f"Current revision {current[0]} != expected head {heads[0]}"
                )

        if len(heads) > 1:
            errors.append(f"Multiple heads: {heads}")

        missing_tables = verify_required_tables(session)
        if missing_tables:
            errors.append(f"Missing tables: {missing_tables}")
        else:
            print("Required tables: OK")

        missing_cols = verify_critical_columns(session)
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")
        else:
            print("Critical columns: OK")

    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  [FAIL] {e}")
        sys.exit(1)

    print("\nSchema verification PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
