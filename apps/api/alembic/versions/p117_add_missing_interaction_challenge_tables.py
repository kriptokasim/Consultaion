"""Create user_interaction, challenge_session, challenge_round tables

Revision ID: p117_add_missing_tables
Revises: p116_add_user_pred_unique
Create Date: 2026-06-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p117_add_missing_tables"
down_revision: Union[str, None] = "p116_add_user_pred_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenge_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_challenge_session_debate_id", "challenge_session", ["debate_id"], unique=False)
    op.create_index("ix_challenge_session_user_id", "challenge_session", ["user_id"], unique=False)
    op.create_index("ix_challenge_session_status", "challenge_session", ["status"], unique=False)

    op.create_table(
        "challenge_round",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("user_pushback", sa.Text(), nullable=False),
        sa.Column("model_response", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.String(), nullable=False),
        sa.Column("revised_synthesis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["challenge_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_challenge_round_session_id", "challenge_round", ["session_id"], unique=False)
    op.create_index("ix_challenge_round_round_index", "challenge_round", ["round_index"], unique=False)

    op.create_table(
        "user_interaction",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=True),
        sa.Column("interaction_type", sa.String(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_interaction_user_id", "user_interaction", ["user_id"], unique=False)
    op.create_index("ix_user_interaction_debate_id", "user_interaction", ["debate_id"], unique=False)
    op.create_index("ix_user_interaction_interaction_type", "user_interaction", ["interaction_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_interaction_interaction_type", table_name="user_interaction")
    op.drop_index("ix_user_interaction_debate_id", table_name="user_interaction")
    op.drop_index("ix_user_interaction_user_id", table_name="user_interaction")
    op.drop_table("user_interaction")

    op.drop_index("ix_challenge_round_round_index", table_name="challenge_round")
    op.drop_index("ix_challenge_round_session_id", table_name="challenge_round")
    op.drop_table("challenge_round")

    op.drop_index("ix_challenge_session_status", table_name="challenge_session")
    op.drop_index("ix_challenge_session_user_id", table_name="challenge_session")
    op.drop_index("ix_challenge_session_debate_id", table_name="challenge_session")
    op.drop_table("challenge_session")
