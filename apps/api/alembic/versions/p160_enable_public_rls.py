"""P160: protect public PostgreSQL tables with row-level security."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "p160_enable_public_rls"
down_revision: Union[str, None] = "p159_billing_team_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_billing_webhook_events() -> None:
    """Create the webhook idempotency table that the Stripe provider uses."""

    bind = op.get_bind()
    inspector = inspect(bind)
    if "billing_webhook_events" not in inspector.get_table_names():
        op.create_table(
            "billing_webhook_events",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_billing_webhook_events_provider",
            "billing_webhook_events",
            ["provider"],
            unique=False,
        )


def _complete_usage_ledger_state() -> None:
    """Add the settlement fields expected by the billing state machine.

    Historical rows are marked settled so deploying this repair cannot make an
    already-accounted charge refundable a second time. New ORM writes always
    provide an explicit status; PostgreSQL's raw-insert default is reserved.
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    if "usage_ledger_entry" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("usage_ledger_entry")
    }
    additions = {
        "status": sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'settled'"),
        ),
        "debate_id": sa.Column("debate_id", sa.String(), nullable=True),
        "attempt_id": sa.Column("attempt_id", sa.String(), nullable=True),
        "settled_at": sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        "refunded_at": sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in existing_columns:
            op.add_column("usage_ledger_entry", column)

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "usage_ledger_entry",
            "status",
            server_default=sa.text("'reserved'"),
        )

    inspector = inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("usage_ledger_entry")
    }
    for column_name in ("status", "debate_id", "attempt_id"):
        index_name = f"ix_usage_ledger_entry_{column_name}"
        if index_name not in existing_indexes:
            op.create_index(
                index_name,
                "usage_ledger_entry",
                [column_name],
                unique=False,
            )


def _enable_public_table_rls() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                target record;
            BEGIN
                FOR target IN
                    SELECT n.nspname AS schema_name, c.relname AS table_name
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind IN ('r', 'p')
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
                        target.schema_name,
                        target.table_name
                    );
                END LOOP;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    _ensure_billing_webhook_events()
    _complete_usage_ledger_state()
    _enable_public_table_rls()


def downgrade() -> None:
    # RLS is a one-way security hardening. Some public tables may have had RLS
    # enabled before P160, so a blanket disable would silently remove their
    # pre-existing protection. Keep RLS enabled when rolling this revision
    # back; operators can make an explicit, table-scoped policy change if a
    # genuine rollback of row security is ever required.
    # Keep additive billing repairs in place: dropping them would discard
    # settlement history and webhook idempotency records.
    pass
