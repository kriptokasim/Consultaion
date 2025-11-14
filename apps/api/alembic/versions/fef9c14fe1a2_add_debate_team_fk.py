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
    op.add_column("debate", sa.Column("team_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_debate_team_id"), "debate", ["team_id"], unique=False)
    op.create_foreign_key(
        "fk_debate_team_id_team",
        "debate",
        "team",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_debate_team_id_team", "debate", type_="foreignkey")
    op.drop_index(op.f("ix_debate_team_id"), table_name="debate")
    op.drop_column("debate", "team_id")
