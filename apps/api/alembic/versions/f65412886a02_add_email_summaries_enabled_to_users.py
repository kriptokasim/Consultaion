"""add email_summaries_enabled to users

Revision ID: f65412886a02
Revises: e2612470e38a
Create Date: 2025-12-04 12:05:13.724364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f65412886a02'
down_revision: Union[str, None] = 'e2612470e38a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("email_summaries_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user", "email_summaries_enabled")
