"""add panel config to debates

Revision ID: a9a2c7c7db6e
Revises: 409938eb0f98
Create Date: 2025-11-21 22:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a9a2c7c7db6e"
down_revision = "409938eb0f98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("debate", sa.Column("panel_config", sa.JSON(), nullable=True))
    op.add_column("debate", sa.Column("engine_version", sa.String(length=64), nullable=True))

    default_panel = {
        "engine_version": "parliament-v1",
        "seats": [
            {
                "seat_id": "optimist",
                "display_name": "Optimist",
                "provider_key": "openai",
                "model": "openai/gpt-4o-mini",
                "role_profile": "optimist",
                "temperature": 0.7,
            },
            {
                "seat_id": "risk_officer",
                "display_name": "Risk Officer",
                "provider_key": "anthropic",
                "model": "anthropic/claude-3-5-sonnet-20240620",
                "role_profile": "risk_officer",
                "temperature": 0.4,
            },
            {
                "seat_id": "architect",
                "display_name": "Systems Architect",
                "provider_key": "openai",
                "model": "openai/gpt-4o-mini",
                "role_profile": "architect",
                "temperature": 0.5,
            },
        ],
    }

    debate_table = sa.table(
        "debate",
        sa.column("panel_config", sa.JSON()),
        sa.column("engine_version", sa.String(length=64)),
    )
    op.execute(debate_table.update().values(panel_config=default_panel, engine_version="parliament-v1"))


def downgrade() -> None:
    op.drop_column("debate", "engine_version")
    op.drop_column("debate", "panel_config")
