"""Create debate_continuation and debate_stage_checkpoint tables

Revision ID: p118_add_continuation
Revises: p117_add_missing_tables
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p118_add_continuation"
down_revision: Union[str, None] = "p117_add_missing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create debate_continuation table
    op.create_table(
        "debate_continuation",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("debate_id", "idempotency_key", name="uq_debate_continuation_debate_id_idempotency_key")
    )
    op.create_index("ix_debate_continuation_debate_id", "debate_continuation", ["debate_id"], unique=False)

    # 2. Create debate_stage_checkpoint table
    op.create_table(
        "debate_stage_checkpoint",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("stage_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("debate_id", "stage_key", name="uq_debate_stage_checkpoint_debate_id_stage_key")
    )
    op.create_index("ix_debate_stage_checkpoint_debate_id", "debate_stage_checkpoint", ["debate_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_debate_stage_checkpoint_debate_id", table_name="debate_stage_checkpoint")
    op.drop_table("debate_stage_checkpoint")

    op.drop_index("ix_debate_continuation_debate_id", table_name="debate_continuation")
    op.drop_table("debate_continuation")
