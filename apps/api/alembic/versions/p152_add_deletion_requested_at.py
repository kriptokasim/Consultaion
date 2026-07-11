"""Add user.deletion_requested_at for GDPR scheduled deletion workflow.

Revision ID: p152_deletion_requested_at
Revises: p137_continuation_drift
Create Date: 2026-07-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p152_deletion_requested_at"
down_revision: Union[str, None] = "p137_continuation_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "user" in tables:
        columns = [c["name"] for c in inspector.get_columns("user")]

        if "deletion_requested_at" not in columns:
            op.add_column(
                "user",
                sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
            )
            op.create_index(
                "ix_user_deletion_requested_at",
                "user",
                ["deletion_requested_at"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "user" in tables:
        indexes = [idx["name"] for idx in inspector.get_indexes("user")]
        columns = [c["name"] for c in inspector.get_columns("user")]

        if "ix_user_deletion_requested_at" in indexes:
            op.drop_index("ix_user_deletion_requested_at", table_name="user")
        if "deletion_requested_at" in columns:
            op.drop_column("user", "deletion_requested_at")
