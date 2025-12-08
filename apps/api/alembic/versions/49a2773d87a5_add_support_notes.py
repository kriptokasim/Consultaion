"""add_support_notes

Revision ID: 49a2773d87a5
Revises: f427e86669e2
Create Date: 2025-12-08 14:12:21.451422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49a2773d87a5'
down_revision: Union[str, None] = 'f427e86669e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
