"""init tables

Revision ID: bb2c5d45d274
Revises: 
Create Date: 2025-11-11 09:02:08.255989

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb2c5d45d274"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "debate",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_content", sa.Text(), nullable=True),
        sa.Column("final_meta", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "debateround",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], name="fk_debateround_debate_id_debate"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("persona", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], name="fk_message_debate_id_debate"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("persona", sa.String(), nullable=False),
        sa.Column("judge", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], name="fk_score_debate_id_debate"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("rankings", sa.JSON(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], name="fk_vote_debate_id_debate"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("vote")
    op.drop_table("score")
    op.drop_table("message")
    op.drop_table("debateround")
    op.drop_table("debate")
