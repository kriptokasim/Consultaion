"""P165: enforce one local row per provider subscription identity.

Revision ID: p165_billing_provider_unique
Revises: p164_billing_event_fence
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "p165_billing_provider_unique"
down_revision: Union[str, None] = "p164_billing_event_fence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_INDEX = "ix_billing_subscriptions_provider_ref"
UNIQUE_INDEX = "uq_billing_subscriptions_provider_ref"


def upgrade() -> None:
    bind = op.get_bind()

    # Historical schema allowed duplicate local rows for the same Stripe
    # subscription. Collapse them deterministically before adding the DB
    # concurrency authority. Prefer the newest provider event, then the newest
    # local timestamps/period. The first row in each ordered group survives.
    rows = bind.execute(
        sa.text(
            "SELECT id, provider, provider_subscription_id "
            "FROM billing_subscriptions "
            "WHERE provider_subscription_id IS NOT NULL "
            "ORDER BY provider, provider_subscription_id, "
            "CASE WHEN provider_event_created_at IS NULL THEN 1 ELSE 0 END, "
            "provider_event_created_at DESC, updated_at DESC, "
            "current_period_end DESC, created_at DESC"
        )
    ).mappings().all()

    seen: set[tuple[str, str]] = set()
    duplicate_ids = []
    for row in rows:
        identity = (str(row["provider"]), str(row["provider_subscription_id"]))
        if identity in seen:
            duplicate_ids.append(row["id"])
        else:
            seen.add(identity)

    for duplicate_id in duplicate_ids:
        bind.execute(
            sa.text("DELETE FROM billing_subscriptions WHERE id = :id"),
            {"id": duplicate_id},
        )

    indexes = {index["name"] for index in inspect(bind).get_indexes("billing_subscriptions")}
    if OLD_INDEX in indexes:
        op.drop_index(OLD_INDEX, table_name="billing_subscriptions")
    if UNIQUE_INDEX not in indexes:
        op.create_index(
            UNIQUE_INDEX,
            "billing_subscriptions",
            ["provider", "provider_subscription_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in inspect(bind).get_indexes("billing_subscriptions")}
    if UNIQUE_INDEX in indexes:
        op.drop_index(UNIQUE_INDEX, table_name="billing_subscriptions")
    if OLD_INDEX not in indexes:
        op.create_index(
            OLD_INDEX,
            "billing_subscriptions",
            ["provider", "provider_subscription_id"],
            unique=False,
        )
