"""PS158: Message.response_id column + unique (debate_id, response_id).

Revision ID: ps158_message_response_id
Revises: ps157_terminal_transition
Create Date: 2026-07-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "ps158_message_response_id"
down_revision: Union[str, None] = "ps157_terminal_transition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("message")}
    indexes = {ix["name"] for ix in insp.get_indexes("message")}

    if "response_id" not in cols:
        op.add_column("message", sa.Column("response_id", sa.String(), nullable=True))
    if "ix_message_response_id" not in indexes:
        op.create_index("ix_message_response_id", "message", ["response_id"], unique=False)

    # Backfill from JSON meta.response_id when present
    if dialect == "postgresql":
        # meta is JSON (not JSONB) — cast before key existence / ->> extract
        op.execute(
            sa.text(
                "UPDATE message SET response_id = (meta::jsonb)->>'response_id' "
                "WHERE meta IS NOT NULL "
                "AND response_id IS NULL "
                "AND (meta::jsonb) ? 'response_id' "
                "AND ((meta::jsonb)->>'response_id') IS NOT NULL "
                "AND ((meta::jsonb)->>'response_id') <> ''"
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
                    "WHERE meta IS NOT NULL "
                    "AND response_id IS NULL "
                    "AND json_extract(meta, '$.response_id') IS NOT NULL"
                )
            )
        except Exception:
            pass
        if "uq_message_debate_response_id" not in indexes:
            op.create_index(
                "uq_message_debate_response_id",
                "message",
                ["debate_id", "response_id"],
                unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = {ix["name"] for ix in insp.get_indexes("message")}
    cols = {c["name"] for c in insp.get_columns("message")}
    if "uq_message_debate_response_id" in indexes:
        op.drop_index("uq_message_debate_response_id", table_name="message")
    if "ix_message_response_id" in indexes:
        op.drop_index("ix_message_response_id", table_name="message")
    if "response_id" in cols:
        op.drop_column("message", "response_id")
