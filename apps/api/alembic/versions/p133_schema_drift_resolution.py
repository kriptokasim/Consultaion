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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # ── 1. Create usage_ledger_entry table ──────────────────────────────────
    if "usage_ledger_entry" not in tables:
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
    if "usage_counter" in tables:
        usage_counter_cols = [c["name"] for c in inspector.get_columns("usage_counter")]
        if "exports_used" not in usage_counter_cols:
            with op.batch_alter_table("usage_counter") as batch_op:
                batch_op.add_column(sa.Column("exports_used", sa.Integer(), nullable=False, server_default="0"))

    # ── 3. Add account lockout columns to user ──────────────────────────────
    if "user" in tables:
        user_cols = [c["name"] for c in inspector.get_columns("user")]
        with op.batch_alter_table("user") as batch_op:
            if "failed_login_attempts" not in user_cols:
                batch_op.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
            if "locked_until" not in user_cols:
                batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
            if "last_failed_login_at" not in user_cols:
                batch_op.add_column(sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))

    # ── 4. Add reconciliation run_key columns ───────────────────────────────
    if "billing_reconciliation_runs" in tables:
        recon_cols = [c["name"] for c in inspector.get_columns("billing_reconciliation_runs")]
        with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
            if "run_key" not in recon_cols:
                batch_op.add_column(sa.Column("run_key", sa.String(), nullable=True))
            if "window_start" not in recon_cols:
                batch_op.add_column(sa.Column("window_start", sa.DateTime(timezone=True), nullable=True))
            if "window_end" not in recon_cols:
                batch_op.add_column(sa.Column("window_end", sa.DateTime(timezone=True), nullable=True))
            
            existing_indexes = [idx["name"] for idx in inspector.get_indexes("billing_reconciliation_runs")]
            if "ix_billing_reconciliation_runs_run_key" not in existing_indexes:
                batch_op.create_index("ix_billing_reconciliation_runs_run_key", ["run_key"])
            
            existing_uniques = [cons["name"] for cons in inspector.get_unique_constraints("billing_reconciliation_runs")]
            if "uq_billing_reconciliation_runs_run_key" not in existing_uniques:
                batch_op.create_unique_constraint("uq_billing_reconciliation_runs_run_key", ["run_key"])

    # ── 5. Make support_note.user_id nullable (FK repair) ──────────────────
    if "support_note" in tables:
        columns = inspector.get_columns("support_note")
        user_id_col = next((c for c in columns if c["name"] == "user_id"), None)
        if user_id_col and user_id_col.get("nullable", True) is False:
            with op.batch_alter_table("support_note") as batch_op:
                batch_op.alter_column("user_id", nullable=True)

    # ── 6. Drop stale promotions table (removed from models) ────────────────
    if "promotions" in tables:
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("promotions")]
        if "ix_promotions_location" in existing_indexes:
            op.drop_index("ix_promotions_location", table_name="promotions")
        op.drop_table("promotions")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # ── 6. Recreate promotions table ────────────────────────────────────────
    if "promotions" not in tables:
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
    if "support_note" in tables:
        columns = inspector.get_columns("support_note")
        user_id_col = next((c for c in columns if c["name"] == "user_id"), None)
        if user_id_col and user_id_col.get("nullable", True) is True:
            with op.batch_alter_table("support_note") as batch_op:
                batch_op.alter_column("user_id", nullable=False)

    # ── 4. Remove reconciliation run_key columns ───────────────────────────
    if "billing_reconciliation_runs" in tables:
        recon_cols = [c["name"] for c in inspector.get_columns("billing_reconciliation_runs")]
        existing_uniques = [cons["name"] for cons in inspector.get_unique_constraints("billing_reconciliation_runs")]
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("billing_reconciliation_runs")]
        with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
            if "uq_billing_reconciliation_runs_run_key" in existing_uniques:
                batch_op.drop_constraint("uq_billing_reconciliation_runs_run_key", type_="unique")
            if "ix_billing_reconciliation_runs_run_key" in existing_indexes:
                batch_op.drop_index("ix_billing_reconciliation_runs_run_key")
            if "window_end" in recon_cols:
                batch_op.drop_column("window_end")
            if "window_start" in recon_cols:
                batch_op.drop_column("window_start")
            if "run_key" in recon_cols:
                batch_op.drop_column("run_key")

    # ── 3. Remove account lockout columns from user ────────────────────────
    if "user" in tables:
        user_cols = [c["name"] for c in inspector.get_columns("user")]
        with op.batch_alter_table("user") as batch_op:
            if "last_failed_login_at" in user_cols:
                batch_op.drop_column("last_failed_login_at")
            if "locked_until" in user_cols:
                batch_op.drop_column("locked_until")
            if "failed_login_attempts" in user_cols:
                batch_op.drop_column("failed_login_attempts")

    # ── 2. Remove exports_used from usage_counter ──────────────────────────
    if "usage_counter" in tables:
        usage_counter_cols = [c["name"] for c in inspector.get_columns("usage_counter")]
        if "exports_used" in usage_counter_cols:
            with op.batch_alter_table("usage_counter") as batch_op:
                batch_op.drop_column("exports_used")

    # ── 1. Drop usage_ledger_entry table ───────────────────────────────────
    if "usage_ledger_entry" in tables:
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("usage_ledger_entry")]
        if "ix_usage_ledger_user_created" in existing_indexes:
            op.drop_index("ix_usage_ledger_user_created", table_name="usage_ledger_entry")
        op.drop_table("usage_ledger_entry")
