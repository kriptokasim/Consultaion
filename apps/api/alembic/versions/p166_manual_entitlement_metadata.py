"""P166: add explicit metadata for manual entitlement grants.

Revision ID: p166_manual_entitlement_metadata
Revises: p165_billing_subscription_provider_unique
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p166_manual_entitlement_metadata"
down_revision: Union[str, None] = "p165_billing_subscription_provider_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_subscriptions",
        sa.Column("entitlement_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "billing_subscriptions",
        sa.Column("entitlement_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "billing_subscriptions",
        sa.Column("granted_by_user_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_subscriptions", "granted_by_user_id")
    op.drop_column("billing_subscriptions", "entitlement_reason")
    op.drop_column("billing_subscriptions", "entitlement_source")
