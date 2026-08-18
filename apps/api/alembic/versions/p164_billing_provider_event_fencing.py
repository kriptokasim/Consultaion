"""P164: fence billing subscription state by provider event creation time.

Revision ID: p164_billing_event_fence
Revises: p163_recheck_unmanaged_rls
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p164_billing_event_fence"
down_revision: Union[str, None] = "p163_recheck_unmanaged_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_subscriptions",
        sa.Column("provider_event_created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_subscriptions", "provider_event_created_at")
