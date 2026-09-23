"""Restore the promotions runtime table on the current migration lineage.

P133 intentionally removed the old promotions table as stale. The product later
reintroduced the /promotions route and model, but the old 2025 billing/seed
migrations are not ancestors of the current p169 lineage. This forward repair
restores the live contract without rewriting migration history.

Revision ID: p170_promotions_runtime_repair
Revises: p169_oauth_account_binding
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p170_promotions_runtime_repair"
down_revision: Union[str, None] = "p169_oauth_account_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    uuid_type = (
        sa.dialects.postgresql.UUID(as_uuid=True)
        if is_postgres
        else sa.String(length=36)
    )
    uuid_default = sa.text("gen_random_uuid()") if is_postgres else None
    timestamp_default = sa.text("CURRENT_TIMESTAMP")

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "promotions" not in tables:
        op.create_table(
            "promotions",
            sa.Column("id", uuid_type, server_default=uuid_default, nullable=False),
            sa.Column("location", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("cta_label", sa.Text(), nullable=True),
            sa.Column("cta_url", sa.Text(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("100"),
            ),
            sa.Column("target_plan_slug", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=timestamp_default,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=timestamp_default,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("promotions")}
    if "ix_promotions_location_priority" not in indexes:
        op.create_index(
            "ix_promotions_location_priority",
            "promotions",
            ["location", "is_active", "priority"],
            unique=False,
        )

    # This API reads promotions server-side. Keep the public table inaccessible
    # through Supabase's exposed Data API unless an explicit policy is added.
    if is_postgres:
        op.execute("ALTER TABLE promotions ENABLE ROW LEVEL SECURITY")

    op.execute(
        sa.text(
            """
            INSERT INTO promotions
                (id, location, title, body, cta_label, cta_url, is_active,
                 priority, target_plan_slug)
            SELECT gen_random_uuid(), 'dashboard_sidebar', 'Upgrade to Pro',
                   'Increase your monthly debates, unlock exports, and add more models to each run.',
                   'View pricing', '/pricing', TRUE, 10, 'free'
            WHERE NOT EXISTS (
                SELECT 1 FROM promotions
                WHERE location = 'dashboard_sidebar'
                  AND target_plan_slug = 'free'
            )
            """
            if is_postgres
            else
            """
            INSERT INTO promotions
                (id, location, title, body, cta_label, cta_url, is_active,
                 priority, target_plan_slug)
            SELECT lower(hex(randomblob(16))), 'dashboard_sidebar', 'Upgrade to Pro',
                   'Increase your monthly debates, unlock exports, and add more models to each run.',
                   'View pricing', 1, 10, 'free'
            WHERE NOT EXISTS (
                SELECT 1 FROM promotions
                WHERE location = 'dashboard_sidebar'
                  AND target_plan_slug = 'free'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO promotions
                (id, location, title, body, cta_label, cta_url, is_active,
                 priority, target_plan_slug)
            SELECT gen_random_uuid(), 'debate_limit_modal', 'Need more debates?',
                   'Pro members get 100 debates per month plus priority processing.',
                   'Upgrade plan', '/settings/billing', TRUE, 20, 'free'
            WHERE NOT EXISTS (
                SELECT 1 FROM promotions
                WHERE location = 'debate_limit_modal'
                  AND target_plan_slug = 'free'
            )
            """
            if is_postgres
            else
            """
            INSERT INTO promotions
                (id, location, title, body, cta_label, cta_url, is_active,
                 priority, target_plan_slug)
            SELECT lower(hex(randomblob(16))), 'debate_limit_modal', 'Need more debates?',
                   'Pro members get 100 debates per month plus priority processing.',
                   'Upgrade plan', '/settings/billing', 1, 20, 'free'
            WHERE NOT EXISTS (
                SELECT 1 FROM promotions
                WHERE location = 'debate_limit_modal'
                  AND target_plan_slug = 'free'
            )
            """
        )
    )


def downgrade() -> None:
    # Forward repair: do not drop a table that the current application contract
    # depends on merely because an older schema is being downgraded.
    pass
