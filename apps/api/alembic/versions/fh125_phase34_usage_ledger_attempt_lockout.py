"""FH125 Phase 3+4: UsageLedgerEntry, DebateAttempt, exports_used, lockout fields

Revision ID: fh125_phase34
Revises: p124_recon_run_key
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fh125_phase34"
down_revision: Union[str, None] = "p124_recon_run_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # E-5: Add exports_used to usage_counter
    with op.batch_alter_table("usage_counter") as batch_op:
        batch_op.add_column(sa.Column("exports_used", sa.Integer(), nullable=False, server_default="0"))

    # C-5: Add lockout fields to user
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))

    # E-2: Create usage_ledger_entry table
    op.create_table(
        "usage_ledger_entry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_usage_ledger_idempotency"),
        sa.Index("ix_usage_ledger_user_created", "user_id", "created_at"),
    )

    # G-7: Create debate_attempt table
    op.create_table(
        "debate_attempt",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("debate_id", sa.String(), sa.ForeignKey("debate.id"), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, index=True, server_default="queued"),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("debate_attempt")
    op.drop_table("usage_ledger_entry")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("last_failed_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_attempts")

    with op.batch_alter_table("usage_counter") as batch_op:
        batch_op.drop_column("exports_used")
