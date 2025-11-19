"""add billing tables

Revision ID: fb386f1f3bb4
Revises: 7c3f5e5d6c70
Create Date: 2025-11-19 13:32:22.179845

"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "fb386f1f3bb4"
down_revision: Union[str, None] = "7c3f5e5d6c70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = dialect_name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    uuid_type = postgresql.UUID(as_uuid=True) if is_postgres else sa.String(length=36)
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else JSON()
    json_server_default = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")
    uuid_server_default = sa.text("gen_random_uuid()") if is_postgres else None
    timestamp_default = sa.text("now()") if is_postgres else sa.text("CURRENT_TIMESTAMP")

    billing_plans = op.create_table(
        "billing_plans",
        sa.Column("id", uuid_type, server_default=uuid_server_default, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_monthly", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("is_default_free", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("limits", json_type, nullable=False, server_default=json_server_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_billing_plans_slug", "billing_plans", ["slug"], unique=True)
    if is_postgres:
        op.create_index(
            "uq_billing_plans_default_free",
            "billing_plans",
            ["is_default_free"],
            unique=True,
            postgresql_where=sa.text("is_default_free = true"),
        )

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", uuid_type, server_default=uuid_server_default, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("plan_id", uuid_type, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_customer_id", sa.Text(), nullable=True),
        sa.Column("provider_subscription_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_subscriptions_user_id", "billing_subscriptions", ["user_id"], unique=False)
    op.create_index(
        "ix_billing_subscriptions_provider_ref",
        "billing_subscriptions",
        ["provider", "provider_subscription_id"],
        unique=False,
    )

    op.create_table(
        "billing_usage",
        sa.Column("id", uuid_type, server_default=uuid_server_default, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("debates_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("exports_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_used", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("model_tokens", json_type, nullable=False, server_default=json_server_default),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "period", name="uq_billing_usage_user_period"),
    )
    op.create_index("ix_billing_usage_user_period", "billing_usage", ["user_id", "period"], unique=False)

    op.create_table(
        "promotions",
        sa.Column("id", uuid_type, server_default=uuid_server_default, nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.Text(), nullable=True),
        sa.Column("cta_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("target_plan_slug", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_promotions_location_priority",
        "promotions",
        ["location", "is_active", "priority"],
        unique=False,
    )

    plan_table = sa.table(
        "billing_plans",
        sa.column("id", sa.String()),
        sa.column("slug", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("price_monthly", sa.Numeric(10, 2)),
        sa.column("currency", sa.Text()),
        sa.column("is_default_free", sa.Boolean()),
        sa.column("limits", JSON()),
    )

    op.bulk_insert(
        plan_table,
        [
            {
                "id": str(uuid.uuid4()),
                "slug": "free",
                "name": "Free",
                "price_monthly": None,
                "currency": "USD",
                "is_default_free": True,
                "limits": {
                    "max_debates_per_month": 10,
                    "max_models_per_debate": 3,
                    "exports_enabled": False,
                },
            },
            {
                "id": str(uuid.uuid4()),
                "slug": "pro",
                "name": "Pro",
                "price_monthly": Decimal("29.00"),
                "currency": "USD",
                "is_default_free": False,
                "limits": {
                    "max_debates_per_month": 100,
                    "max_models_per_debate": 8,
                    "exports_enabled": True,
                },
            },
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = dialect_name == "postgresql"
    op.drop_index("ix_promotions_location_priority", table_name="promotions")
    op.drop_table("promotions")
    op.drop_index("ix_billing_usage_user_period", table_name="billing_usage")
    op.drop_table("billing_usage")
    op.drop_index("ix_billing_subscriptions_provider_ref", table_name="billing_subscriptions")
    op.drop_index("ix_billing_subscriptions_user_id", table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
    if is_postgres:
        op.drop_index("uq_billing_plans_default_free", table_name="billing_plans")
    op.drop_index("uq_billing_plans_slug", table_name="billing_plans")
    op.drop_table("billing_plans")
