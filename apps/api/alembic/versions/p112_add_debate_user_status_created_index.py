"""Patchset 112: Replace debate user/status index with covering index

Revision ID: p112_idx_001
Revises: a1b2c3d4e5f6
Create Date: 2026-03-09

Replaces ix_debate_user_status (user_id, status) with
ix_debate_user_status_created (user_id, status, created_at)
to optimize the common list_debates query which filters by user_id/status
and orders by created_at DESC.

The new index is a superset that covers both:
1. WHERE user_id = ? AND status = ? (original use case)
2. WHERE user_id = ? AND status = ? ORDER BY created_at DESC (list_debates)

This avoids index duplication while improving query performance.

Query pattern verified:
  SELECT * FROM debate
  WHERE user_id = ? AND status = ?
  ORDER BY created_at DESC
  LIMIT ? OFFSET ?
"""
from typing import Sequence, Union

from alembic import op

revision: str = "p112_idx_001"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing partial index first
    # Note: This index was defined in models.py __table_args__ but the new one supersedes it
    op.drop_index("ix_debate_user_status", table_name="debate", if_exists=True)

    # Add covering composite index optimized for list_debates ORDER BY
    # This covers: WHERE user_id = ? AND status = ? ORDER BY created_at DESC
    op.create_index(
        "ix_debate_user_status_created",
        "debate",
        ["user_id", "status", "created_at"],
        unique=False,
        # Note: PostgreSQL supports DESC in index, but SQLite does not.
        # The index still helps with range scans even without explicit DESC.
    )


def downgrade() -> None:
    op.drop_index("ix_debate_user_status_created", table_name="debate")
    # Restore original index
    op.create_index(
        "ix_debate_user_status",
        "debate",
        ["user_id", "status"],
        unique=False,
    )
