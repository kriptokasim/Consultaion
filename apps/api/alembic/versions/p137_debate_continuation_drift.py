"""Resolve schema drift on debate_continuation by conditionally adding columns and keys.

Revision ID: p137_continuation_drift
Revises: 4cae97704905
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p137_continuation_drift"
down_revision: Union[str, None] = "4cae97704905"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "debate_continuation" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate_continuation")]
        
        with op.batch_alter_table("debate_continuation") as batch_op:
            if "cancelled_at" not in columns:
                batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
            if "paused_at" not in columns:
                batch_op.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
            if "failure_code" not in columns:
                batch_op.add_column(sa.Column("failure_code", sa.String(), nullable=True))
            if "failure_detail_safe" not in columns:
                batch_op.add_column(sa.Column("failure_detail_safe", sa.Text(), nullable=True))
            if "credit_reservation_id" not in columns:
                batch_op.add_column(sa.Column("credit_reservation_id", sa.String(), nullable=True))
            if "retry_of_continuation_id" not in columns:
                batch_op.add_column(sa.Column("retry_of_continuation_id", sa.String(), nullable=True))

            existing_indexes = [idx["name"] for idx in inspector.get_indexes("debate_continuation")]
            if "ix_debate_continuation_retry_of" not in existing_indexes:
                batch_op.create_index("ix_debate_continuation_retry_of", ["retry_of_continuation_id"], unique=False)
            
            fks = inspector.get_foreign_keys("debate_continuation")
            fk_cols = []
            for fk in fks:
                fk_cols.extend(fk["constrained_columns"])
            
            if "retry_of_continuation_id" not in fk_cols:
                batch_op.create_foreign_key(
                    "fk_debate_continuation_retry_of_continuation_id",
                    "debate_continuation",
                    ["retry_of_continuation_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "debate_continuation" in tables:
        columns = [c["name"] for c in inspector.get_columns("debate_continuation")]
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("debate_continuation")]
        fks = inspector.get_foreign_keys("debate_continuation")
        fk_cols = []
        for fk in fks:
            fk_cols.extend(fk["constrained_columns"])

        with op.batch_alter_table("debate_continuation") as batch_op:
            if "retry_of_continuation_id" in fk_cols:
                fk_name = next((fk["name"] for fk in fks if "retry_of_continuation_id" in fk["constrained_columns"]), None)
                if fk_name:
                    batch_op.drop_constraint(fk_name, type_="foreignkey")
                else:
                    batch_op.drop_constraint("fk_debate_continuation_retry_of_continuation_id", type_="foreignkey")

            if "ix_debate_continuation_retry_of" in existing_indexes:
                batch_op.drop_index("ix_debate_continuation_retry_of")

            if "retry_of_continuation_id" in columns:
                batch_op.drop_column("retry_of_continuation_id")
            if "credit_reservation_id" in columns:
                batch_op.drop_column("credit_reservation_id")
            if "failure_detail_safe" in columns:
                batch_op.drop_column("failure_detail_safe")
            if "failure_code" in columns:
                batch_op.drop_column("failure_code")
            if "paused_at" in columns:
                batch_op.drop_column("paused_at")
            if "cancelled_at" in columns:
                batch_op.drop_column("cancelled_at")
