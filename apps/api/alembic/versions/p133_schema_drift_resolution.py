"""Resolve schema drift — add missing tables, columns, indexes; remove stale promotions

Revision ID: p133_schema_drift_resolution
Revises: fh125_attempt_integration
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p133_schema_drift_resolution"
down_revision: Union[str, None] = "fh125_attempt_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create usage_ledger_entry table ──────────────────────────────────
    op.create_table(
        "usage_ledger_entry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_ledger_user_created", "usage_ledger_entry", ["user_id", "created_at"])

    # ── 2. Add exports_used to usage_counter ────────────────────────────────
    with op.batch_alter_table("usage_counter") as batch_op:
        batch_op.add_column(sa.Column("exports_used", sa.Integer(), nullable=False, server_default="0"))

    # ── 3. Add account lockout columns to user ──────────────────────────────
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))

    # ── 4. Add reconciliation run_key columns ───────────────────────────────
    with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
        batch_op.add_column(sa.Column("run_key", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("window_start", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("window_end", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_billing_reconciliation_runs_run_key", ["run_key"])
        batch_op.create_unique_constraint("uq_billing_reconciliation_runs_run_key", ["run_key"])

    # ── 5. Make support_note.user_id nullable (FK repair) ──────────────────
    with op.batch_alter_table("support_note") as batch_op:
        batch_op.alter_column("user_id", nullable=True)

    # ── 6. Drop stale promotions table (removed from models) ────────────────
    op.drop_index("ix_promotions_location", table_name="promotions")
    op.drop_table("promotions")


def downgrade() -> None:
    # ── 6. Recreate promotions table ────────────────────────────────────────
    op.create_table(
        "promotions",
        sa.Column("id", sa.CHAR(length=32), primary_key=True),
        sa.Column("location", sa.VARCHAR(), nullable=False),
        sa.Column("title", sa.VARCHAR(), nullable=False),
        sa.Column("body", sa.VARCHAR(), nullable=False),
        sa.Column("cta_label", sa.VARCHAR(), nullable=True),
        sa.Column("cta_url", sa.VARCHAR(), nullable=True),
        sa.Column("is_active", sa.BOOLEAN(), nullable=False),
        sa.Column("priority", sa.INTEGER(), nullable=False),
        sa.Column("target_plan_slug", sa.VARCHAR(), nullable=True),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("updated_at", sa.DATETIME(), nullable=False),
    )
    op.create_index("ix_promotions_location", "promotions", ["location"])

    # ── 5. Make support_note.user_id non-nullable ──────────────────────────
    with op.batch_alter_table("support_note") as batch_op:
        batch_op.alter_column("user_id", nullable=False)

    # ── 4. Remove reconciliation run_key columns ───────────────────────────
    with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
        batch_op.drop_constraint("uq_billing_reconciliation_runs_run_key", type_="unique")
        batch_op.drop_index("ix_billing_reconciliation_runs_run_key")
        batch_op.drop_column("window_end")
        batch_op.drop_column("window_start")
        batch_op.drop_column("run_key")

    # ── 3. Remove account lockout columns from user ────────────────────────
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("last_failed_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_attempts")

    # ── 2. Remove exports_used from usage_counter ──────────────────────────
    with op.batch_alter_table("usage_counter") as batch_op:
        batch_op.drop_column("exports_used")

    # ── 1. Drop usage_ledger_entry table ───────────────────────────────────
    op.drop_index("ix_usage_ledger_user_created", table_name="usage_ledger_entry")
    op.drop_table("usage_ledger_entry")
