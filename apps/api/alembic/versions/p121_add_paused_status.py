"""Add paused_at and retry_of_continuation_id to debate_continuation

Revision ID: p121_add_paused_status
Revises: p120_add_missing_tables
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p121_add_paused_status"
down_revision: Union[str, None] = "p120_add_missing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("debate_continuation", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("debate_continuation", sa.Column("retry_of_continuation_id", sa.String(), nullable=True))
    op.create_index("ix_debate_continuation_retry_of", "debate_continuation", ["retry_of_continuation_id"], unique=False)
    op.create_index("ix_debate_continuation_debate_status", "debate_continuation", ["debate_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_debate_continuation_debate_status", table_name="debate_continuation")
    op.drop_index("ix_debate_continuation_retry_of", table_name="debate_continuation")
    op.drop_column("debate_continuation", "retry_of_continuation_id")
    op.drop_column("debate_continuation", "paused_at")
