"""Create missing tables: llm_usage_log, divergence_report, debate_turn, vote_record, red_team_session, oracle_session, oracle_branch, user_provider_keys

Revision ID: p120_add_missing_tables
Revises: p119_extend_continuation
Create Date: 2026-06-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p120_add_missing_tables"
down_revision: Union[str, None] = "p119_extend_continuation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("gateway", sa.String(), nullable=True),
        sa.Column("model_pool", sa.String(), nullable=True),
        sa.Column("routing_policy", sa.String(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fallback_reason", sa.String(), nullable=True),
        sa.Column("user_plan", sa.String(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_log_debate", "llm_usage_log", ["debate_id"], unique=False)
    op.create_index("ix_llm_usage_log_user", "llm_usage_log", ["user_id"], unique=False)
    op.create_index("ix_llm_usage_log_provider_model", "llm_usage_log", ["provider", "model"], unique=False)
    op.create_index("ix_llm_usage_log_created", "llm_usage_log", ["created_at"], unique=False)
    op.create_index("ix_llm_usage_log_provider", "llm_usage_log", ["provider"], unique=False)
    op.create_index("ix_llm_usage_log_model", "llm_usage_log", ["model"], unique=False)

    op.create_table(
        "divergence_report",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("divergence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consensus_claims", sa.JSON(), nullable=True),
        sa.Column("contested_claims", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_divergence_report_debate_id", "divergence_report", ["debate_id"], unique=True)

    op.create_table(
        "debate_turn",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("claims_nodes", sa.JSON(), nullable=True),
        sa.Column("position_drift", sa.JSON(), nullable=True),
        sa.Column("moderation_steering", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debate_turn_debate_id", "debate_turn", ["debate_id"], unique=False)
    op.create_index("ix_debate_turn_round_index", "debate_turn", ["round_index"], unique=False)
    op.create_index("ix_debate_turn_agent_id", "debate_turn", ["agent_id"], unique=False)

    op.create_table(
        "vote_record",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("vote_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vote_record_debate_id", "vote_record", ["debate_id"], unique=False)
    op.create_index("ix_vote_record_user_id", "vote_record", ["user_id"], unique=False)

    op.create_table(
        "red_team_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("debate_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("proposal_text", sa.Text(), nullable=False),
        sa.Column("lenses", sa.JSON(), nullable=True),
        sa.Column("critique_matrix", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["debate_id"], ["debate.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_red_team_session_debate_id", "red_team_session", ["debate_id"], unique=False)
    op.create_index("ix_red_team_session_user_id", "red_team_session", ["user_id"], unique=False)

    op.create_table(
        "oracle_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oracle_session_user_id", "oracle_session", ["user_id"], unique=False)
    op.create_index("ix_oracle_session_status", "oracle_session", ["status"], unique=False)

    op.create_table(
        "oracle_branch",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("parent_branch_id", sa.String(), nullable=True),
        sa.Column("assumption_text", sa.Text(), nullable=False),
        sa.Column("reasoning_nodes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["oracle_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oracle_branch_session_id", "oracle_branch", ["session_id"], unique=False)
    op.create_index("ix_oracle_branch_parent_branch_id", "oracle_branch", ["parent_branch_id"], unique=False)

    op.create_table(
        "user_provider_keys",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("masked_key", sa.String(), nullable=False),
        sa.Column("encrypted_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_provider_keys_user_id", "user_provider_keys", ["user_id"], unique=False)
    op.create_index("ix_user_provider_keys_provider", "user_provider_keys", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_provider_keys_provider", table_name="user_provider_keys")
    op.drop_index("ix_user_provider_keys_user_id", table_name="user_provider_keys")
    op.drop_table("user_provider_keys")

    op.drop_index("ix_oracle_branch_parent_branch_id", table_name="oracle_branch")
    op.drop_index("ix_oracle_branch_session_id", table_name="oracle_branch")
    op.drop_table("oracle_branch")

    op.drop_index("ix_oracle_session_status", table_name="oracle_session")
    op.drop_index("ix_oracle_session_user_id", table_name="oracle_session")
    op.drop_table("oracle_session")

    op.drop_index("ix_red_team_session_user_id", table_name="red_team_session")
    op.drop_index("ix_red_team_session_debate_id", table_name="red_team_session")
    op.drop_table("red_team_session")

    op.drop_index("ix_vote_record_user_id", table_name="vote_record")
    op.drop_index("ix_vote_record_debate_id", table_name="vote_record")
    op.drop_table("vote_record")

    op.drop_index("ix_debate_turn_agent_id", table_name="debate_turn")
    op.drop_index("ix_debate_turn_round_index", table_name="debate_turn")
    op.drop_index("ix_debate_turn_debate_id", table_name="debate_turn")
    op.drop_table("debate_turn")

    op.drop_index("ix_divergence_report_debate_id", table_name="divergence_report")
    op.drop_table("divergence_report")

    op.drop_index("ix_llm_usage_log_model", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_provider", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_created", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_provider_model", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_user", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_debate", table_name="llm_usage_log")
    op.drop_table("llm_usage_log")
