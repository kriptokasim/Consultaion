"""Add hosted credits columns to User

Revision ID: p114_add_user_hosted_credits
Revises: p113_add_gateway_policy
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "p114_add_user_hosted_credits"
down_revision: Union[str, None] = "p113_add_gateway_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hosted_credits_limit", sa.Integer(), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("hosted_credits_used", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("hosted_credit_source", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="signup"))


def downgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("hosted_credits_limit")
        batch_op.drop_column("hosted_credits_used")
        batch_op.drop_column("hosted_credit_source")
