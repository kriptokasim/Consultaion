"""Add run_key, window_start, window_end to billing_reconciliation_runs

Revision ID: p124_recon_run_key
Revises: p123_cont_retry_fk
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p124_recon_run_key"
down_revision: Union[str, None] = "p123_cont_retry_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
        batch_op.add_column(
            sa.Column("run_key", sa.String(128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_billing_reconciliation_runs_run_key",
            ["run_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("billing_reconciliation_runs") as batch_op:
        batch_op.drop_constraint("uq_billing_reconciliation_runs_run_key", type_="unique")
        batch_op.drop_column("window_end")
        batch_op.drop_column("window_start")
        batch_op.drop_column("run_key")
