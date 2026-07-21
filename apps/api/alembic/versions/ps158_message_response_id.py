"""PS158: Message.response_id column + unique (debate_id, response_id).

Revision ID: ps158_message_response_id
Revises: ps157_terminal_transition
Create Date: 2026-07-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ps158_message_response_id"
down_revision: Union[str, None] = "ps157_terminal_transition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("message", sa.Column("response_id", sa.String(), nullable=True))
    op.create_index("ix_message_response_id", "message", ["response_id"], unique=False)

    # Backfill from JSON meta.response_id when present
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "UPDATE message SET response_id = meta->>'response_id' "
                "WHERE meta IS NOT NULL AND meta ? 'response_id' "
                "AND (meta->>'response_id') IS NOT NULL AND (meta->>'response_id') <> ''"
            )
        )
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_message_debate_response_id "
                "ON message (debate_id, response_id) "
                "WHERE response_id IS NOT NULL"
            )
        )
    else:
        # SQLite / other: best-effort JSON extract; unique via plain unique index
        # (SQLite allows multiple NULLs in UNIQUE columns)
        try:
            op.execute(
                sa.text(
                    "UPDATE message SET response_id = json_extract(meta, '$.response_id') "
                    "WHERE meta IS NOT NULL AND json_extract(meta, '$.response_id') IS NOT NULL"
                )
            )
        except Exception:
            pass
        op.create_index(
            "uq_message_debate_response_id",
            "message",
            ["debate_id", "response_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_message_debate_response_id", table_name="message")
    op.drop_index("ix_message_response_id", table_name="message")
    op.drop_column("message", "response_id")
