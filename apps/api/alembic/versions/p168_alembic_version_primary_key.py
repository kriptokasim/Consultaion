"""P168: restore the alembic_version single-row primary key.

Revision ID: p168_alembic_version_pk
Revises: p167_referral_attribution

Deployments bootstrapped by services/migration_safety.ensure_alembic_version_table
got a version table without the primary key Alembic's own bootstrap creates, so
concurrent release jobs could each insert a revision row. Adding the key makes
the single-row invariant a database guarantee again.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "p168_alembic_version_pk"
down_revision: Union[str, None] = "p167_referral_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERSION_TABLE = "alembic_version"
PK_NAME = "alembic_version_pkc"


def _has_primary_key(bind: sa.engine.Connection) -> bool:
    pk = inspect(bind).get_pk_constraint(VERSION_TABLE)
    return bool(pk and pk.get("constrained_columns"))


def upgrade() -> None:
    bind = op.get_bind()
    if VERSION_TABLE not in inspect(bind).get_table_names():
        return
    if _has_primary_key(bind):
        return

    # A primary key cannot be added over duplicates, and choosing a survivor
    # here would silently discard the record of which revision the schema
    # actually matches. Fail loudly and let an operator decide.
    rows = [
        row[0]
        for row in bind.execute(sa.text("SELECT version_num FROM alembic_version"))
    ]
    if len(rows) > 1:
        raise RuntimeError(
            f"alembic_version holds {len(rows)} rows ({sorted(rows)}) but a "
            "primary key permits at most one. Two release jobs bootstrapped the "
            "table concurrently. Confirm which revision the schema really "
            "matches, run DELETE FROM alembic_version WHERE version_num <> "
            "'<correct>'; and re-run the migration."
        )

    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
            )
        )
    elif dialect == "sqlite":
        # SQLite cannot add a constraint in place; rebuild and swap. The row
        # count is already known to be 0 or 1, so the copy is exact.
        op.execute(sa.text("DROP TABLE IF EXISTS alembic_version_pk_rebuild"))
        op.execute(
            sa.text(
                "CREATE TABLE alembic_version_pk_rebuild ("
                "    version_num VARCHAR(128) NOT NULL, "
                "    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        op.execute(
            sa.text(
                "INSERT INTO alembic_version_pk_rebuild (version_num) "
                "SELECT version_num FROM alembic_version"
            )
        )
        op.execute(sa.text("DROP TABLE alembic_version"))
        op.execute(
            sa.text("ALTER TABLE alembic_version_pk_rebuild RENAME TO alembic_version")
        )


def downgrade() -> None:
    bind = op.get_bind()
    if VERSION_TABLE not in inspect(bind).get_table_names():
        return
    if not _has_primary_key(bind):
        return
    # Only PostgreSQL can drop the constraint in place. Rebuilding the SQLite
    # version table purely to reintroduce the defect is not worth doing, so the
    # key stays there.
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "DROP CONSTRAINT IF EXISTS alembic_version_pkc"
            )
        )
