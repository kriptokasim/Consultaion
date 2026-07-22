"""P160: additive billing repairs for the backend-only database model."""

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

    - completed/completed_with_warnings work → settled
    - running/scheduled/queued work → reserved (still in-flight)
    - failed/cancelled or unidentifiable historical work → reconciliation_pending

    A migration cannot prove that the user counter was decremented for an old
    failed reservation, so it must never label such a row ``refunded``.  The
    quarantine state prevents duplicate automatic refunds while preserving the
    row for explicit reconciliation.
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    if "usage_ledger_entry" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("usage_ledger_entry")
    }
    status_was_missing = "status" not in existing_columns
    additions = {
        "status": sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'reconciliation_pending'"),
        ),
        "debate_id": sa.Column("debate_id", sa.String(), nullable=True),
        "attempt_id": sa.Column("attempt_id", sa.String(), nullable=True),
        "settled_at": sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        "refunded_at": sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in existing_columns:
            op.add_column("usage_ledger_entry", column)

    # Backfill status based on associated debate/continuation state.  This is
    # deliberately PostgreSQL-specific because the production drift repair is
    # for PostgreSQL; SQLite keeps the safe quarantine default.
    if bind.dialect.name == "postgresql":
        debate_exists = "debate" in inspector.get_table_names()
        if debate_exists:
            if status_was_missing:
                # Non-reservation ledger rows are historical usage facts, not
                # open hosted-credit liabilities.
                op.execute(sa.text(
                    "UPDATE usage_ledger_entry SET status = 'settled' "
                    "WHERE kind <> 'credit_reservation'"
                ))

            # Continuation reservations use the continuation's terminal state,
            # never the Debate's later global status.
            continuation_exists = "debate_continuation" in inspector.get_table_names()
            if continuation_exists:
                op.execute(sa.text(
                    "UPDATE usage_ledger_entry AS ule SET status = 'settled' "
                    "FROM debate_continuation AS dc "
                    "WHERE ule.kind = 'credit_reservation' "
                    "AND NULLIF(ule.meta ->> 'continuation_id', '') = dc.id "
                    "AND dc.debate_id = ule.debate_id "
                    "AND dc.credit_reservation_id = ule.id "
                    "AND dc.status = 'completed' "
                    "AND ule.status NOT IN ('refunded', 'settled')"
                ))
                op.execute(sa.text(
                    "UPDATE usage_ledger_entry AS ule SET status = 'reserved' "
                    "FROM debate_continuation AS dc "
                    "WHERE ule.kind = 'credit_reservation' "
                    "AND NULLIF(ule.meta ->> 'continuation_id', '') = dc.id "
                    "AND dc.debate_id = ule.debate_id "
                    "AND dc.credit_reservation_id = ule.id "
                    "AND dc.status IN ('requested', 'preflight_passed', 'dispatched', 'running', 'paused') "
                    "AND ule.status NOT IN ('refunded', 'settled')"
                ))
                op.execute(sa.text(
                    "UPDATE usage_ledger_entry AS ule "
                    "SET status = 'reconciliation_pending' "
                    "FROM debate_continuation AS dc "
                    "WHERE ule.kind = 'credit_reservation' "
                    "AND NULLIF(ule.meta ->> 'continuation_id', '') = dc.id "
                    "AND dc.debate_id = ule.debate_id "
                    "AND dc.credit_reservation_id = ule.id "
                    "AND dc.status IN ('failed', 'cancelled') "
                    "AND (ule.status <> 'refunded' OR ule.refunded_at IS NULL)"
                ))

            # Initial reservations have no continuation identity and must match
            # Debate.credit_reservation_id before they can be classified.
            op.execute(sa.text(
                "UPDATE usage_ledger_entry AS ule SET status = 'settled' "
                "FROM debate AS d "
                "WHERE ule.kind = 'credit_reservation' "
                "AND COALESCE(ule.meta ->> 'continuation_id', '') = '' "
                "AND d.id = ule.debate_id "
                "AND d.credit_reservation_id = ule.id "
                "AND d.status IN ('completed', 'completed_with_warnings') "
                "AND ule.status NOT IN ('refunded', 'settled')"
            ))
            op.execute(sa.text(
                "UPDATE usage_ledger_entry AS ule SET status = 'reserved' "
                "FROM debate AS d "
                "WHERE ule.kind = 'credit_reservation' "
                "AND COALESCE(ule.meta ->> 'continuation_id', '') = '' "
                "AND d.id = ule.debate_id "
                "AND d.credit_reservation_id = ule.id "
                "AND d.status NOT IN ('completed', 'completed_with_warnings', 'failed', 'cancelled') "
                "AND ule.status NOT IN ('refunded', 'settled')"
            ))
            op.execute(sa.text(
                "UPDATE usage_ledger_entry AS ule "
                "SET status = 'reconciliation_pending' "
                "FROM debate AS d "
                "WHERE ule.kind = 'credit_reservation' "
                "AND COALESCE(ule.meta ->> 'continuation_id', '') = '' "
                "AND d.id = ule.debate_id "
                "AND d.credit_reservation_id = ule.id "
                "AND d.status IN ('failed', 'cancelled') "
                "AND (ule.status <> 'refunded' OR ule.refunded_at IS NULL)"
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
