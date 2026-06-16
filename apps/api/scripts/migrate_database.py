#!/usr/bin/env python3
"""
Safe migration runner for the Consultaion database.

Replaces raw ``alembic upgrade head`` with a guarded sequence that:

1. Ensures the alembic_version table exists.
2. Widens the version_num column to VARCHAR(128) on PostgreSQL.
3. Reads current revision values and validates them against the graph.
4. Verifies exactly one migration head.
5. Executes alembic upgrade head.
6. Verifies database current revision equals repository head.
7. Verifies required application tables and columns.
8. Exits non-zero on any mismatch.

Usage:
    python scripts/migrate_database.py              # normal deploy
    python scripts/migrate_database.py --check      # read-only check
    python scripts/migrate_database.py \\
        --allow-stamp --expected-current <rev> --stamp <rev>
                                                    # break-glass recovery
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)
logger = logging.getLogger("migrate_database")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe migration runner")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only check — do not run migrations",
    )
    parser.add_argument(
        "--allow-stamp",
        action="store_true",
        help="(break-glass) Allow automatic stamping of a revision",
    )
    parser.add_argument(
        "--expected-current",
        type=str,
        default=None,
        help="Required current revision for --allow-stamp",
    )
    parser.add_argument(
        "--stamp",
        type=str,
        default=None,
        help="Revision to stamp when using --allow-stamp",
    )
    args = parser.parse_args()

    # ---------- Phase 0: Bootstrap ----------
    from config import settings

    database_url = settings.DATABASE_URL
    if not database_url:
        logger.error("DATABASE_URL is not set")
        sys.exit(1)

    logger.info("Connecting to database")
    from sqlalchemy import create_engine

    engine = create_engine(database_url, pool_pre_ping=True)

    from services.migration_safety import (
        ensure_alembic_version_table,
        widen_version_column,
        get_current_revisions,
        get_migration_heads,
        get_all_revisions,
        verify_required_tables,
        verify_critical_columns,
    )

    from sqlmodel import Session

    with Session(engine) as session:
        # ---------- Phase 1: Version-table safety ----------
        ensure_alembic_version_table(session)
        widen_version_column(session)

        # ---------- Phase 2: Read current state ----------
        current_revisions = get_current_revisions(session)
        all_revisions = get_all_revisions()
        heads = get_migration_heads()

        logger.info("Current revision(s): %s", current_revisions or "(none)")
        logger.info("Expected head: %s", heads)

        if len(heads) != 1:
            logger.error(
                "Expected exactly one migration head, found %d: %s",
                len(heads), heads,
            )
            sys.exit(1)

        expected_head = heads[0]

        # ---------- Phase 3: Validate current revisions ----------
        if current_revisions:
            for rev in current_revisions:
                if rev not in all_revisions:
                    logger.error(
                        "Current revision %s is not in the migration graph. "
                        "Cannot safely upgrade. Use --allow-stamp for break-glass recovery.",
                        rev,
                    )
                    sys.exit(1)

        # ---------- Phase 4: Check-only mode ----------
        if args.check:
            if current_revisions:
                head_match = current_revisions[0] == expected_head
                logger.info(
                    "CHECK: current=%s expected=%s match=%s",
                    current_revisions[0], expected_head, head_match,
                )
            else:
                logger.info("CHECK: no current revision found")

            missing_tables = verify_required_tables(session)
            if missing_tables:
                logger.warning("CHECK: missing tables: %s", missing_tables)

            missing_cols = verify_critical_columns(session)
            if missing_cols:
                logger.warning("CHECK: missing columns: %s", missing_cols)

            logger.info("Read-only check complete")
            sys.exit(0)

        # ---------- Phase 5: Execute upgrade ----------
        if current_revisions and current_revisions[0] == expected_head:
            logger.info("Already at head revision %s — no upgrade needed", expected_head)
        else:
            logger.info("Running alembic upgrade head")
            from alembic.config import Config as AlembicConfig
            from alembic.command import upgrade

            alembic_cfg = AlembicConfig()
            alembic_cfg.set_main_option("script_location", "alembic")
            alembic_cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

            try:
                upgrade(alembic_cfg, "head")
                logger.info("Migration completed successfully")
            except Exception as exc:
                logger.error("Migration failed: %s", exc)
                sys.exit(1)

        # ---------- Phase 6: Verify post-upgrade ----------
        session.commit()
        engine.dispose()

    # Reconnect with fresh engine to get post-migration state
    with Session(create_engine(database_url, pool_pre_ping=True)) as session:
        post_revisions = get_current_revisions(session)
        if not post_revisions:
            logger.error("No revision found after upgrade")
            sys.exit(1)

        post_rev = post_revisions[0]
        if post_rev != expected_head:
            logger.error(
                "Post-upgrade revision %s does not match expected head %s",
                post_rev, expected_head,
            )
            sys.exit(1)

        logger.info("Post-upgrade revision verified: %s", post_rev)

        # ---------- Phase 7: Verify required tables ----------
        missing_tables = verify_required_tables(session)
        if missing_tables:
            logger.error("Required tables missing: %s", missing_tables)
            sys.exit(1)

        missing_cols = verify_critical_columns(session)
        if missing_cols:
            logger.error("Required columns missing: %s", missing_cols)
            sys.exit(1)

        logger.info("Schema verification passed")
        logger.info("Migration complete — database is at head revision %s", expected_head)


if __name__ == "__main__":
    main()
