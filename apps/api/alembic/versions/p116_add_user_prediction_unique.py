"""Add unique constraint on (debate_id, user_id) for UserPrediction

Revision ID: p116_add_user_pred_unique
Revises: p115_add_apikey_expire_fields
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p116_add_user_pred_unique"
down_revision: Union[str, None] = "p115_add_apikey_expire_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, deduplicate existing rows — keep the newest prediction per (debate_id, user_id)
    op.execute("""
        DELETE FROM user_prediction
        WHERE id NOT IN (
            SELECT DISTINCT ON (debate_id, user_id) id
            FROM user_prediction
            ORDER BY debate_id, user_id, created_at DESC
        )
    """)
    # Then add the unique constraint
    op.create_unique_constraint(
        "uq_user_prediction_debate_user",
        "user_prediction",
        ["debate_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_prediction_debate_user", "user_prediction", type_="unique")
