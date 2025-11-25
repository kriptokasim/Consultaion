"""add pairwise_vote and rating_persona tables

Revision ID: 7c3f5e5d6c70
Revises: 5c2a4761c5d9
Create Date: 2025-02-14 13:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7c3f5e5d6c70"
down_revision = "5c2a4761c5d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pairwise_vote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("candidate_a", sa.String(), nullable=False),
        sa.Column("candidate_b", sa.String(), nullable=False),
        sa.Column("winner", sa.String(), nullable=False),
        sa.Column("judge_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pairwise_vote_debate_id", "pairwise_vote", ["debate_id"], unique=False)
    op.create_index("ix_pairwise_vote_category", "pairwise_vote", ["category"], unique=False)
    op.create_index("ix_pairwise_vote_winner", "pairwise_vote", ["winner"], unique=False)
    op.create_index("ix_pairwise_vote_candidate_a_candidate_b", "pairwise_vote", ["candidate_a", "candidate_b"], unique=False)
    op.create_index("ix_pairwise_vote_judge_id", "pairwise_vote", ["judge_id"], unique=False)

    op.create_table(
        "rating_persona",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("persona", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("elo", sa.Float(), nullable=False),
        sa.Column("stdev", sa.Float(), nullable=False),
        sa.Column("n_matches", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("ci_low", sa.Float(), nullable=False),
        sa.Column("ci_high", sa.Float(), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rating_persona_persona", "rating_persona", ["persona"], unique=False)
    op.create_index("ix_rating_persona_category", "rating_persona", ["category"], unique=False)
    op.create_index("ix_rating_persona_unique", "rating_persona", ["persona", "category"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_rating_persona_unique", table_name="rating_persona")
    op.drop_index("ix_rating_persona_category", table_name="rating_persona")
    op.drop_index("ix_rating_persona_persona", table_name="rating_persona")
    op.drop_table("rating_persona")
    op.drop_index("ix_pairwise_vote_judge_id", table_name="pairwise_vote")
    op.drop_index("ix_pairwise_vote_candidate_a_candidate_b", table_name="pairwise_vote")
    op.drop_index("ix_pairwise_vote_winner", table_name="pairwise_vote")
    op.drop_index("ix_pairwise_vote_category", table_name="pairwise_vote")
    op.drop_index("ix_pairwise_vote_debate_id", table_name="pairwise_vote")
    op.drop_table("pairwise_vote")
