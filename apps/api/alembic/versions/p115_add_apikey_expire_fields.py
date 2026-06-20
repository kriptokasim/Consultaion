"""Add expiration and rotation fields to APIKey

Revision ID: p115_add_apikey_expire_fields
Revises: p114_add_user_hosted_credits
Create Date: 2026-06-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p115_add_apikey_expire_fields"
down_revision: Union[str, None] = "p114_add_user_hosted_credits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("api_keys", schema=None) as batch_op:
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rotation_reminder_sent", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("api_keys", schema=None) as batch_op:
        batch_op.drop_column("expires_at")
        batch_op.drop_column("rotation_reminder_sent")
