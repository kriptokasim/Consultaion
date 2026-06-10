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
    # Create the table if it doesn't exist — was never created via migration,
    # only via SQLModel.create_all on SQLite (skipped on PostgreSQL/Render)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_prediction (
            id VARCHAR NOT NULL,
            debate_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            predicted_winner VARCHAR NOT NULL,
            confidence_score FLOAT DEFAULT 0.0,
            is_locked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            is_correct BOOLEAN,
            PRIMARY KEY (id)
        )
    """)
    op.create_index("ix_user_prediction_debate_id", "user_prediction", ["debate_id"], unique=False, if_not_exists=True)
    op.create_index("ix_user_prediction_user_id", "user_prediction", ["user_id"], unique=False, if_not_exists=True)
    # Deduplicate existing rows — keep the newest prediction per (debate_id, user_id)
    op.execute("""
        DELETE FROM user_prediction
        WHERE id NOT IN (
            SELECT DISTINCT ON (debate_id, user_id) id
            FROM user_prediction
            ORDER BY debate_id, user_id, created_at DESC
        )
    """)
    # Then add the unique constraint (if not already present)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_prediction_debate_user'
            ) THEN
                ALTER TABLE user_prediction
                ADD CONSTRAINT uq_user_prediction_debate_user UNIQUE (debate_id, user_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE user_prediction DROP CONSTRAINT IF EXISTS uq_user_prediction_debate_user")
