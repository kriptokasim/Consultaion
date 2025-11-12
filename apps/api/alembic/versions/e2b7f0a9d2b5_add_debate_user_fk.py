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
    op.add_column("debate", sa.Column("user_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_debate_user_id"), "debate", ["user_id"], unique=False)
    op.create_foreign_key("fk_debate_user_id_user", "debate", "user", ["user_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_debate_user_id_user", "debate", type_="foreignkey")
    op.drop_index(op.f("ix_debate_user_id"), table_name="debate")
    op.drop_column("debate", "user_id")
