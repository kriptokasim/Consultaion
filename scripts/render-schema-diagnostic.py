#!/usr/bin/env python3
"""
Render Schema Diagnostic — prints schema state without credentials.

Usage:
    python scripts/render-schema-diagnostic.py [--url DATABASE_URL]

If --url is omitted, reads from DATABASE_URL env var or defaults to
the AppSettings value.
"""

from __future__ import annotations

import argparse
import os
import sys


def mask_url(url: str) -> str:
    """Mask credentials in a database URL for safe printing."""
    if "@" in url:
        prefix, rest = url.split("@", 1)
        if "://" in prefix:
            scheme, creds = prefix.split("://", 1)
            return f"{scheme}://****:****@{rest}"
        return f"****:****@{rest}"
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Schema diagnostic")
    parser.add_argument("--url", type=str, default=None, help="Database URL")
    args = parser.parse_args()

    if args.url:
        database_url = args.url
    else:
        from config import settings
        database_url = settings.DATABASE_URL

    if not database_url:
        print("ERROR: DATABASE_URL is not set")
        sys.exit(1)

    print(f"Database URL: {mask_url(database_url)}")

    try:
        from sqlalchemy import create_engine, inspect, text
        engine = create_engine(database_url, pool_pre_ping=True)
    except Exception as exc:
        print(f"ERROR: Cannot connect: {exc}")
        sys.exit(1)

    dialect = engine.dialect.name
    print(f"Dialect: {dialect}")

    from services.migration_safety import (
        ensure_alembic_version_table,
        widen_version_column,
        get_current_revisions,
        get_migration_heads,
        verify_required_tables,
        verify_critical_columns,
    )

    from sqlmodel import Session

    with Session(engine) as session:
        ensure_alembic_version_table(session)

        # Version column info
        inspector = inspect(session.get_bind())
        if "alembic_version" in inspector.get_table_names():
            cols = inspector.get_columns("alembic_version")
            for c in cols:
                if c["name"] == "version_num":
                    print(f"version_num type: {c['type']}")
                    try:
                        result = session.execute(
                            text(
                                "SELECT character_maximum_length "
                                "FROM information_schema.columns "
                                "WHERE table_name='alembic_version' "
                                "AND column_name='version_num'"
                            )
                        ).scalar()
                        if result:
                            print(f"version_num max length: {result}")
                    except Exception:
                        pass
        else:
            print("alembic_version table: MISSING")

        current_revisions = get_current_revisions(session)
        heads = get_migration_heads()

        print(f"Current revision(s): {current_revisions or '(none)'}")
        print(f"Expected head(s): {heads}")

        if current_revisions and heads:
            match = current_revisions[0] == heads[0]
            print(f"At head: {match}")

        missing_tables = verify_required_tables(session)
        if missing_tables:
            print(f"Missing tables: {missing_tables}")
        else:
            print("Required tables: ALL PRESENT")

        missing_cols = verify_critical_columns(session)
        if missing_cols:
            print(f"Missing critical columns: {missing_cols}")
        else:
            print("Critical columns: ALL PRESENT")

    print()
    print("Diagnostic complete")


if __name__ == "__main__":
    main()
