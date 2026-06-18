"""Add attempt_id to Message, Score, DebateRound and unique constraint to DebateAttempt

Revision ID: fh125_attempt_integration
Revises: fh125_provider_encryption
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fh125_attempt_integration"
down_revision: Union[str, None] = "fh125_provider_encryption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add attempt_id to Message
    with op.batch_alter_table("message") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.String(), nullable=True))
        batch_op.create_index("ix_message_attempt_id", ["attempt_id"])

    # Add attempt_id to Score
    with op.batch_alter_table("score") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.String(), nullable=True))
        batch_op.create_index("ix_score_attempt_id", ["attempt_id"])

    # Add attempt_id to DebateRound
    with op.batch_alter_table("debate_round") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.String(), nullable=True))
        batch_op.create_index("ix_debate_round_attempt_id", ["attempt_id"])

    # Add unique constraint to DebateAttempt
    op.create_unique_constraint(
        "uq_debate_attempt_debate_number",
        "debate_attempt",
        ["debate_id", "attempt_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_debate_attempt_debate_number", "debate_attempt", type_="unique")

    with op.batch_alter_table("debate_round") as batch_op:
        batch_op.drop_index("ix_debate_round_attempt_id")
        batch_op.drop_column("attempt_id")

    with op.batch_alter_table("score") as batch_op:
        batch_op.drop_index("ix_score_attempt_id")
        batch_op.drop_column("attempt_id")

    with op.batch_alter_table("message") as batch_op:
        batch_op.drop_index("ix_message_attempt_id")
        batch_op.drop_column("attempt_id")
