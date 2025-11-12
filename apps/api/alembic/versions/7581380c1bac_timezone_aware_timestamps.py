"""timezone aware timestamps

Revision ID: 7581380c1bac
Revises: cdb8cc8aa732
Create Date: 2025-11-11 16:12:35.529715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7581380c1bac'
down_revision: Union[str, None] = 'cdb8cc8aa732'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for table, column in [
        ("debate", "created_at"),
        ("debate", "updated_at"),
        ("debateround", "started_at"),
        ("debateround", "ended_at"),
        ("message", "created_at"),
        ("score", "created_at"),
        ("vote", "created_at"),
    ]:
        op.alter_column(table, column, type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for table, column in [
        ("debate", "created_at"),
        ("debate", "updated_at"),
        ("debateround", "started_at"),
        ("debateround", "ended_at"),
        ("message", "created_at"),
        ("score", "created_at"),
        ("vote", "created_at"),
    ]:
        op.alter_column(table, column, type_=sa.DateTime(timezone=False))
