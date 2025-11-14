"""add debate team foreign key

Revision ID: fef9c14fe1a2
Revises: f4a2c1186a2d
Create Date: 2025-11-14 13:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fef9c14fe1a2"
down_revision: Union[str, None] = "f4a2c1186a2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("team_id", sa.String(), nullable=True))
        batch_op.create_index("ix_debate_team_id", ["team_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_debate_team_id_team",
            referent_table="team",
            local_cols=["team_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("debate", schema=None) as batch_op:
        batch_op.drop_constraint("fk_debate_team_id_team", type_="foreignkey")
        batch_op.drop_index("ix_debate_team_id")
        batch_op.drop_column("team_id")
