"""add usage quota and counter tables

Revision ID: 4b1b303e55a8
Revises: fef9c14fe1a2
Create Date: 2025-02-14 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4b1b303e55a8"
down_revision = "fef9c14fe1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_quota",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_quota_user_period", "usage_quota", ["user_id", "period"], unique=True
    )

    op.create_table(
        "usage_counter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("runs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_counter_user_period", "usage_counter", ["user_id", "period"], unique=True
    )


def downgrade():
    op.drop_index("ix_usage_counter_user_period", table_name="usage_counter")
    op.drop_table("usage_counter")
    op.drop_index("ix_usage_quota_user_period", table_name="usage_quota")
    op.drop_table("usage_quota")
