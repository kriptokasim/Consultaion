"""Create billing reconciliation tables

Revision ID: p122_billing_reconciliation
Revises: p121_add_paused_status
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p122_billing_reconciliation"
down_revision: Union[str, None] = "p121_add_paused_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "billing_reconciliation_runs" not in tables:
        op.create_table(
            "billing_reconciliation_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("period", sa.String(), nullable=False),
            sa.Column("run_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="running"),
            sa.Column("users_checked", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("discrepancies_found", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens_internal", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens_usage", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.String(500), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_billing_reconciliation_runs_period", "billing_reconciliation_runs", ["period"], unique=False)
        op.create_index("ix_billing_reconciliation_runs_status", "billing_reconciliation_runs", ["status"], unique=False)

    if "billing_reconciliation_discrepancies" not in tables:
        op.create_table(
            "billing_reconciliation_discrepancies",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("discrepancy_type", sa.String(), nullable=False),
            sa.Column("internal_value", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expected_value", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("severity", sa.String(), nullable=False, server_default="warning"),
            sa.Column("details", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["billing_reconciliation_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_billing_reconciliation_discrepancies_run_id", "billing_reconciliation_discrepancies", ["run_id"], unique=False)
        op.create_index("ix_billing_reconciliation_discrepancies_user_id", "billing_reconciliation_discrepancies", ["user_id"], unique=False)
        op.create_index("ix_billing_reconciliation_discrepancies_severity", "billing_reconciliation_discrepancies", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_billing_reconciliation_discrepancies_severity", table_name="billing_reconciliation_discrepancies")
    op.drop_index("ix_billing_reconciliation_discrepancies_user_id", table_name="billing_reconciliation_discrepancies")
    op.drop_index("ix_billing_reconciliation_discrepancies_run_id", table_name="billing_reconciliation_discrepancies")
    op.drop_table("billing_reconciliation_discrepancies")

    op.drop_index("ix_billing_reconciliation_runs_status", table_name="billing_reconciliation_runs")
    op.drop_index("ix_billing_reconciliation_runs_period", table_name="billing_reconciliation_runs")
    op.drop_table("billing_reconciliation_runs")
