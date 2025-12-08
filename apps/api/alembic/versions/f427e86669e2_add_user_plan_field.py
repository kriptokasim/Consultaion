"""add_user_plan_field

Revision ID: f427e86669e2
Revises: c26f9dd9b7da
Create Date: 2025-12-08 14:00:09.061472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f427e86669e2'
down_revision: Union[str, None] = 'c26f9dd9b7da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
