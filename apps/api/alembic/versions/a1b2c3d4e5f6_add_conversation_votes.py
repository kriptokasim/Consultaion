"""add conversation_votes table

Patchset 77: Add conversation_votes table for Conversation V2 voting.

Revision ID: a1b2c3d4e5f6
Revises: a5ca64b21960
Create Date: 2025-12-20 08:20:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'a5ca64b21960'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'conversation_votes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('vote', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='fk_conversation_votes_user'),
    )
    
    # Create indexes
    op.create_index('ix_conversation_votes_conversation', 'conversation_votes', ['conversation_id'])
    op.create_index('ix_conversation_votes_message', 'conversation_votes', ['message_id'])
    op.create_index('ix_conversation_votes_user', 'conversation_votes', ['user_id'])
    op.create_index(
        'ix_conversation_votes_unique', 
        'conversation_votes', 
        ['conversation_id', 'message_id', 'user_id'], 
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_conversation_votes_unique', table_name='conversation_votes')
    op.drop_index('ix_conversation_votes_user', table_name='conversation_votes')
    op.drop_index('ix_conversation_votes_message', table_name='conversation_votes')
    op.drop_index('ix_conversation_votes_conversation', table_name='conversation_votes')
    op.drop_table('conversation_votes')
