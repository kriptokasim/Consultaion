"""P167: add token-hash referral attribution.

Revision ID: p167_referral_attribution
Revises: p166_manual_entitlement_metadata
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p167_referral_attribution"
down_revision: Union[str, None] = "p166_manual_entitlement_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referral_attributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by_user_id", sa.String(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["claimed_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_referral_attributions_token_hash"),
    )
    op.create_index(
        "ix_referral_attributions_token_hash",
        "referral_attributions",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        "ix_referral_attributions_debate_id",
        "referral_attributions",
        ["debate_id"],
        unique=False,
    )
    op.create_index(
        "ix_referral_attributions_created_by_user_id",
        "referral_attributions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_referral_attributions_claimed_by_user_id",
        "referral_attributions",
        ["claimed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_referral_attributions_expires_at",
        "referral_attributions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_referral_attributions_expires_at", table_name="referral_attributions")
    op.drop_index("ix_referral_attributions_claimed_by_user_id", table_name="referral_attributions")
    op.drop_index("ix_referral_attributions_created_by_user_id", table_name="referral_attributions")
    op.drop_index("ix_referral_attributions_debate_id", table_name="referral_attributions")
    op.drop_index("ix_referral_attributions_token_hash", table_name="referral_attributions")
    op.drop_table("referral_attributions")
