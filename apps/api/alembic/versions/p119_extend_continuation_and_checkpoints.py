"""Extend debate_continuation and debate_stage_checkpoint tables

Revision ID: p119_extend_continuation
Revises: p118_add_continuation
Create Date: 2026-06-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p119_extend_continuation"
down_revision: Union[str, None] = "p118_add_continuation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create/alter debate_continuation
    if "debate_continuation" not in tables:
        op.create_table(
            "debate_continuation",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("debate_id", sa.String(), nullable=False),
            sa.Column("idempotency_key", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="requested"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("target", sa.String(), nullable=True),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("preflight_passed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failure_code", sa.String(), nullable=True),
            sa.Column("failure_detail_safe", sa.Text(), nullable=True),
            sa.Column("credit_reservation_id", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("debate_id", "idempotency_key", name="uq_debate_continuation_debate_id_idempotency_key")
        )
        op.create_index("ix_debate_continuation_debate_id", "debate_continuation", ["debate_id"], unique=False)
    else:
        columns = [c["name"] for c in inspector.get_columns("debate_continuation")]
        if "user_id" not in columns:
            op.add_column("debate_continuation", sa.Column("user_id", sa.String(), nullable=True))
        if "target" not in columns:
            op.add_column("debate_continuation", sa.Column("target", sa.String(), nullable=True))
        if "requested_at" not in columns:
            op.add_column("debate_continuation", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
        if "preflight_passed_at" not in columns:
            op.add_column("debate_continuation", sa.Column("preflight_passed_at", sa.DateTime(timezone=True), nullable=True))
        if "dispatched_at" not in columns:
            op.add_column("debate_continuation", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
        if "started_at" not in columns:
            op.add_column("debate_continuation", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        if "completed_at" not in columns:
            op.add_column("debate_continuation", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        if "failed_at" not in columns:
            op.add_column("debate_continuation", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
        if "failure_code" not in columns:
            op.add_column("debate_continuation", sa.Column("failure_code", sa.String(), nullable=True))
        if "failure_detail_safe" not in columns:
            op.add_column("debate_continuation", sa.Column("failure_detail_safe", sa.Text(), nullable=True))
        if "credit_reservation_id" not in columns:
            op.add_column("debate_continuation", sa.Column("credit_reservation_id", sa.String(), nullable=True))
        
        if "user_id" not in columns:
            with op.batch_alter_table("debate_continuation") as batch_op:
                batch_op.create_foreign_key(
                    "fk_debate_continuation_user_id",
                    "user",
                    ["user_id"],
                    ["id"],
                    ondelete="CASCADE"
                )

    # 2. Create/alter debate_stage_checkpoint
    if "debate_stage_checkpoint" not in tables:
        op.create_table(
            "debate_stage_checkpoint",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("debate_id", sa.String(), nullable=False),
            sa.Column("stage_key", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("input_hash", sa.String(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("execution_metadata", sa.JSON(), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("output_reference", sa.Text(), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["debate_id"], ["debate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("debate_id", "stage_key", name="uq_debate_stage_checkpoint_debate_id_stage_key")
        )
        op.create_index("ix_debate_stage_checkpoint_debate_id", "debate_stage_checkpoint", ["debate_id"], unique=False)
    else:
        columns = [c["name"] for c in inspector.get_columns("debate_stage_checkpoint")]
        if "attempt" not in columns:
            op.add_column("debate_stage_checkpoint", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        if "output_reference" not in columns:
            op.add_column("debate_stage_checkpoint", sa.Column("output_reference", sa.Text(), nullable=True))
        if "failed_at" not in columns:
            op.add_column("debate_stage_checkpoint", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
        if "error_code" not in columns:
            op.add_column("debate_stage_checkpoint", sa.Column("error_code", sa.String(), nullable=True))


def downgrade() -> None:
    # Safely drop columns using batch operations
    with op.batch_alter_table("debate_continuation") as batch_op:
        try:
            batch_op.drop_constraint("fk_debate_continuation_user_id", type_="foreignkey")
        except Exception:
            pass
        batch_op.drop_column("credit_reservation_id")
        batch_op.drop_column("failure_detail_safe")
        batch_op.drop_column("failure_code")
        batch_op.drop_column("failed_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("dispatched_at")
        batch_op.drop_column("preflight_passed_at")
        batch_op.drop_column("requested_at")
        batch_op.drop_column("target")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("debate_stage_checkpoint") as batch_op:
        batch_op.drop_column("error_code")
        batch_op.drop_column("failed_at")
        batch_op.drop_column("output_reference")
        batch_op.drop_column("attempt")
