"""add_gin_indexes_to_debate_config

Revision ID: ffc07156de2e
Revises: 1ed74bc6cf9b
Create Date: 2025-12-08 15:55:37.423990

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ffc07156de2e"
down_revision: Union[str, None] = "1ed74bc6cf9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we are running on Postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # GIN indexes require JSONB type with an operator class
        # Cast JSON to JSONB and use jsonb_path_ops for efficient containment queries
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_debate_config_gin ON debate "
            "USING GIN ((config::jsonb) jsonb_path_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_debate_panel_config_gin ON debate "
            "USING GIN ((panel_config::jsonb) jsonb_path_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_debate_panel_config_gin")
        op.execute("DROP INDEX IF EXISTS ix_debate_config_gin")
