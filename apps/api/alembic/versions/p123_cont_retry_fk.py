"""Add foreign key from retry_of_continuation_id to debate_continuation.id

Revision ID: p123_cont_retry_fk
Revises: p122_billing_reconciliation
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p123_cont_retry_fk"
down_revision: Union[str, None] = "p122_billing_reconciliation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("debate_continuation") as batch_op:
        batch_op.create_foreign_key(
            "fk_debate_continuation_retry_of_continuation_id",
            "debate_continuation",
            ["retry_of_continuation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("debate_continuation") as batch_op:
        batch_op.drop_constraint("fk_debate_continuation_retry_of_continuation_id", type_="foreignkey")
