"""PS157 Track M: TerminalTransition table for idempotent side-effect claiming.

Revision ID: ps157_terminal_transition
Revises: p156_execution_fencing
Create Date: 2026-07-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ps157_terminal_transition"
down_revision: Union[str, None] = "p156_execution_fencing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "terminal_transition",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("debate_id", sa.String(), sa.ForeignKey("debate.id"), nullable=False),
        sa.Column("transition_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="claimed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("debate_id", "transition_type", name="uq_terminal_transition_debate_type"),
        sa.Index("ix_terminal_transition_debate_id", "debate_id"),
    )


def downgrade() -> None:
    op.drop_table("terminal_transition")
