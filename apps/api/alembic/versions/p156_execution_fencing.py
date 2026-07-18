"""PS156: Execution fencing — execution_started_at on debate, ownership/fencing
fields on debate_stage_checkpoint, supporting indexes.

Revision ID: p156_execution_fencing
Revises: p155_lease_epoch_fencing
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p156_execution_fencing"
down_revision: Union[str, None] = "p155_lease_epoch_fencing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # --- debate table ---
    if "debate" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate")]

        if "execution_started_at" not in columns:
            with op.batch_alter_table("debate") as batch_op:
                batch_op.add_column(
                    sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True)
                )

        if "ix_debate_runner_epoch" not in _index_names(inspector, "debate"):
            op.create_index("ix_debate_runner_epoch", "debate", ["runner_id", "lease_epoch"])

    # --- debate_stage_checkpoint table ---
    if "debate_stage_checkpoint" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate_stage_checkpoint")]

        with op.batch_alter_table("debate_stage_checkpoint") as batch_op:
            if "lease_epoch" not in columns:
                batch_op.add_column(sa.Column("lease_epoch", sa.Integer(), nullable=True))
            if "updated_at" not in columns:
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
            if "heartbeat_at" not in columns:
                batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

        # Backfill updated_at from started_at for existing rows
        if "updated_at" not in columns:
            op.execute(
                sa.text(
                    "UPDATE debate_stage_checkpoint SET updated_at = started_at "
                    "WHERE updated_at IS NULL"
                )
            )

        # Re-inspect after alterations before creating the index
        inspector = sa.inspect(conn)
        if "ix_checkpoint_status_updated" not in _index_names(inspector, "debate_stage_checkpoint"):
            op.create_index(
                "ix_checkpoint_status_updated",
                "debate_stage_checkpoint",
                ["status", "updated_at"],
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "debate_stage_checkpoint" in tables:
        if "ix_checkpoint_status_updated" in _index_names(inspector, "debate_stage_checkpoint"):
            op.drop_index("ix_checkpoint_status_updated", table_name="debate_stage_checkpoint")
        columns = [c["name"] for c in inspector.get_columns("debate_stage_checkpoint")]
        with op.batch_alter_table("debate_stage_checkpoint") as batch_op:
            if "heartbeat_at" in columns:
                batch_op.drop_column("heartbeat_at")
            if "updated_at" in columns:
                batch_op.drop_column("updated_at")
            if "lease_epoch" in columns:
                batch_op.drop_column("lease_epoch")

    if "debate" in tables:
        if "ix_debate_runner_epoch" in _index_names(inspector, "debate"):
            op.drop_index("ix_debate_runner_epoch", table_name="debate")
        columns = [c["name"] for c in inspector.get_columns("debate")]
        with op.batch_alter_table("debate") as batch_op:
            if "execution_started_at" in columns:
                batch_op.drop_column("execution_started_at")
