"""seed promotions

Revision ID: 5744a0e5e5f7
Revises: fb386f1f3bb4
Create Date: 2025-11-19 14:13:27.766306

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "5744a0e5e5f7"
down_revision: Union[str, None] = "fb386f1f3bb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = dialect_name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgres else sa.String(length=36)
    promotion_table = sa.table(
        "promotions",
        sa.column("id", uuid_type),
        sa.column("location", sa.Text()),
        sa.column("title", sa.Text()),
        sa.column("body", sa.Text()),
        sa.column("cta_label", sa.Text()),
        sa.column("cta_url", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("priority", sa.Integer()),
        sa.column("target_plan_slug", sa.Text()),
    )
    op.bulk_insert(
        promotion_table,
        [
            {
                "id": str(uuid.uuid4()),
                "location": "dashboard_sidebar",
                "title": "Upgrade to Pro",
                "body": "Increase your monthly debates, unlock exports, and add more models to each run.",
                "cta_label": "View pricing",
                "cta_url": "/pricing",
                "is_active": True,
                "priority": 10,
                "target_plan_slug": "free",
            },
            {
                "id": str(uuid.uuid4()),
                "location": "debate_limit_modal",
                "title": "Need more debates?",
                "body": "Pro members get 100 debates per month plus priority processing.",
                "cta_label": "Upgrade plan",
                "cta_url": "/settings/billing",
                "is_active": True,
                "priority": 20,
                "target_plan_slug": "free",
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM promotions WHERE location IN ('dashboard_sidebar','debate_limit_modal')")
