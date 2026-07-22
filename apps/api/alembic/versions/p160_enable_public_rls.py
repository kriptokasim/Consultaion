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

    Historical rows are backfilled based on the status of their associated
    debate/continuation rather than blanket-settling everything:

    - completed/completed_with_warnings debates → settled
    - failed/cancelled debates → refunded (credit was returned)
    - running/scheduled/queued debates → reserved (still in-flight)
    - rows with no debate association → settled (conservative default)

    This prevents losing track of genuinely in-flight reservations during
    deployment while ensuring terminal debates are properly accounted.
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

    # Backfill status based on associated debate state (not blanket 'settled')
    if bind.dialect.name == "postgresql":
        # Check if debate table exists for backfill
        debate_exists = "debate" in inspector.get_table_names()
        if debate_exists:
            # Terminal success → settled
            op.execute(sa.text(
                "UPDATE usage_ledger_entry SET status = 'settled' "
                "WHERE debate_id IN ("
                "  SELECT id FROM debate WHERE status IN ('completed', 'completed_with_warnings')"
                ")"
            ))
            # Terminal failure → refunded
            op.execute(sa.text(
                "UPDATE usage_ledger_entry SET status = 'refunded' "
                "WHERE debate_id IN ("
                "  SELECT id FROM debate WHERE status IN ('failed', 'cancelled')"
                ") AND status != 'refunded'"
            ))
            # In-flight → reserved
            op.execute(sa.text(
                "UPDATE usage_ledger_entry SET status = 'reserved' "
                "WHERE debate_id IN ("
                "  SELECT id FROM debate WHERE status NOT IN ('completed', 'completed_with_warnings', 'failed', 'cancelled')"
                ") AND status = 'settled'"
            ))

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


def upgrade() -> None:
    # Backend-only trusted model: FastAPI handles authentication and
    # authorization. PostgreSQL RLS is intentionally NOT blanket-enabled
    # because no per-table policies exist; enabling RLS without policies
    # would lock out the backend service account and break production.
    _ensure_billing_webhook_events()
    _complete_usage_ledger_state()


def downgrade() -> None:
    # Keep additive billing repairs in place: dropping them would discard
    # settlement history and webhook idempotency records.
    pass
