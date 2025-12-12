"""add_composite_indexes

Revision ID: 39d7c48bb53f
Revises: ffc07156de2e
Create Date: 2025-12-12 13:01:01.033763

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39d7c48bb53f"
down_revision: Union[str, None] = "ffc07156de2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_debate_user_status",
        "debate",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_user_created",
        "audit_log",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_user_created", table_name="audit_log")
    op.drop_index("ix_debate_user_status", table_name="debate")
