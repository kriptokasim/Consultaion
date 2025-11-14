"""add debate.user_id foreign key

Revision ID: e2b7f0a9d2b5
Revises: d1a6c2a8c1e1
Create Date: 2025-02-15 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2b7f0a9d2b5"
down_revision: Union[str, None] = "d1a6c2a8c1e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
        batch_op.create_index("ix_debate_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_debate_user_id_user",
            referent_table="user",
            local_cols=["user_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.drop_constraint("fk_debate_user_id_user", type_="foreignkey")
        batch_op.drop_index("ix_debate_user_id")
        batch_op.drop_column("user_id")
