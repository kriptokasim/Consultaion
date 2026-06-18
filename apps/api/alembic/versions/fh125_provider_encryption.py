"""Add encryption columns to user_provider_keys

Revision ID: fh125_provider_encryption
Revises: fh125_phase34
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fh125_provider_encryption"
down_revision: Union[str, None] = "fh125_phase34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_provider_keys") as batch_op:
        batch_op.add_column(sa.Column("encryption_nonce", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("encryption_key_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("key_fingerprint", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_user_provider_keys_user_provider", ["user_id", "provider"])

    # Backfill existing rows with default values
    op.execute("UPDATE user_provider_keys SET encryption_nonce = '', encryption_key_version = 0, key_fingerprint = '' WHERE encryption_nonce IS NULL")

    # Now make non-nullable
    with op.batch_alter_table("user_provider_keys") as batch_op:
        batch_op.alter_column("encryption_nonce", nullable=False)
        batch_op.alter_column("encryption_key_version", nullable=False)
        batch_op.alter_column("key_fingerprint", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("user_provider_keys") as batch_op:
        batch_op.drop_constraint("uq_user_provider_keys_user_provider", type_="unique")
        batch_op.drop_column("key_fingerprint")
        batch_op.drop_column("encryption_key_version")
        batch_op.drop_column("encryption_nonce")
