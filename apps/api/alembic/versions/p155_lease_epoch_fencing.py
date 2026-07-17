"""PS155.1: Add lease_epoch and execution_owner_id to debate, owner_id to debate_stage_checkpoint.

Revision ID: p155_lease_epoch_fencing
Revises: p152_deletion_requested_at
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p155_lease_epoch_fencing"
down_revision: Union[str, None] = "p152_deletion_requested_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # --- debate table ---
    if "debate" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate")]

        if "lease_epoch" not in columns:
            op.add_column(
                "debate",
                sa.Column("lease_epoch", sa.Integer(), nullable=False, server_default="0"),
            )

        if "execution_owner_id" not in columns:
            op.add_column(
                "debate",
                sa.Column("execution_owner_id", sa.Text(), nullable=True),
            )

    # --- debate_stage_checkpoint table ---
    if "debate_stage_checkpoint" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate_stage_checkpoint")]

        if "owner_id" not in columns:
            op.add_column(
                "debate_stage_checkpoint",
                sa.Column("owner_id", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "debate_stage_checkpoint" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate_stage_checkpoint")]
        if "owner_id" in columns:
            op.drop_column("debate_stage_checkpoint", "owner_id")

    if "debate" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate")]
        if "execution_owner_id" in columns:
            op.drop_column("debate", "execution_owner_id")
        if "lease_epoch" in columns:
            op.drop_column("debate", "lease_epoch")
