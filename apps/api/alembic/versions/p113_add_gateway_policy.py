"""Add gateway_policy to debate

Revision ID: p113_add_gateway_policy
Revises: p112_idx_001
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "p113_add_gateway_policy"
down_revision: Union[str, None] = "p112_idx_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("gateway_policy", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.drop_column("gateway_policy")
