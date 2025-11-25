"""add team tables

Revision ID: f4a2c1186a2d
Revises: e2b7f0a9d2b5
Create Date: 2025-11-14 13:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a2c1186a2d"
down_revision: Union[str, None] = "e2b7f0a9d2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "team_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_member_team_id"), "team_member", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_member_user_id"), "team_member", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_team_member_user_id"), table_name="team_member")
    op.drop_index(op.f("ix_team_member_team_id"), table_name="team_member")
    op.drop_table("team_member")
    op.drop_table("team")
