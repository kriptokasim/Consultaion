"""add_debate_checkpoint

Revision ID: 1187c6c5915d
Revises: 39d7c48bb53f
Create Date: 2025-12-13 15:20:24.238809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1187c6c5915d'
down_revision: Union[str, None] = '39d7c48bb53f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'debate_checkpoint',
        sa.Column('id', sa.String, primary_key=True, nullable=False),
        sa.Column('debate_id', sa.String, sa.ForeignKey('debate.id'), nullable=False, index=True),
        sa.Column('step', sa.String, nullable=False, index=True),
        sa.Column('step_index', sa.Integer, nullable=False, default=0),
        sa.Column('round_index', sa.Integer, nullable=False, default=0),
        sa.Column('status', sa.String, nullable=False, default='running', index=True),
        sa.Column('attempt_count', sa.Integer, nullable=False, default=0),
        sa.Column('resume_token', sa.String, nullable=True, index=True),
        sa.Column('resume_claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checkpoint_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('context_meta', sa.JSON, nullable=True),
    )
    
    # Additional composite index for cleanup queries
    op.create_index(
        'ix_debate_checkpoint_status_last_checkpoint',
        'debate_checkpoint',
        ['status', 'last_checkpoint_at']
    )


def downgrade() -> None:
    op.drop_index('ix_debate_checkpoint_status_last_checkpoint', table_name='debate_checkpoint')
    op.drop_table('debate_checkpoint')
