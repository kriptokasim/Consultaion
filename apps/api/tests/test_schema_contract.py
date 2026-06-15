import pytest
from sqlalchemy import inspect
from sqlmodel import Session, select
import database
from models import (
    User,
    SupportNote,
    DebateError,
    DebateCheckpoint,
    APIKey,
    Debate,
    DebateRound,
    Message,
    Score,
    Vote,
    Team,
    TeamMember,
    UsageQuota,
    UsageCounter,
    AuditLog,
    PairwiseVote,
    RatingPersona,
    AdminEvent,
    ConversationVote,
    LLMUsageLog,
    DivergenceReport,
    DebateTurn,
    UserPrediction,
    VoteRecord,
    RedTeamSession,
    OracleSession,
    OracleBranch,
    ChallengeSession,
    ChallengeRound,
    UserInteraction,
    UserProviderKey,
    DebateContinuation,
    DebateStageCheckpoint,
)

def test_database_table_existence():
    """Verify that all core schema tables exist in the database metadata and active schema."""
    inspector = inspect(database.engine)
    existing_tables = inspector.get_table_names()
    
    expected_tables = {
        "user",
        "support_note",
        "debate_error",
        "debate_checkpoint",
        "api_keys",
        "debate",
        "debateround",
        "message",
        "score",
        "vote",
        "team",
        "team_member",
        "usage_quota",
        "usage_counter",
        "audit_log",
        "pairwise_vote",
        "rating_persona",
        "admin_event",
        "conversation_votes",
        "llm_usage_log",
        "divergence_report",
        "debate_turn",
        "user_prediction",
        "vote_record",
        "red_team_session",
        "oracle_session",
        "oracle_branch",
        "challenge_session",
        "challenge_round",
        "user_interaction",
        "user_provider_keys",
        "debate_continuation",
        "debate_stage_checkpoint",
    }
    
    for table in expected_tables:
        assert table in existing_tables, f"Table '{table}' is missing from the database."

def test_debate_continuation_schema_contract():
    """Verify the columns and types of the debate_continuation table."""
    inspector = inspect(database.engine)
    columns = {col["name"]: col["type"] for col in inspector.get_columns("debate_continuation")}
    
    expected_fields = {
        "id",
        "debate_id",
        "idempotency_key",
        "status",
        "created_at",
        "updated_at",
        "user_id",
        "target",
        "requested_at",
        "preflight_passed_at",
        "dispatched_at",
        "started_at",
        "completed_at",
        "failed_at",
        "failure_code",
        "failure_detail_safe",
        "credit_reservation_id",
    }
    
    for field in expected_fields:
        assert field in columns, f"Field '{field}' is missing from debate_continuation schema."

def test_debate_stage_checkpoint_schema_contract():
    """Verify the columns and types of the debate_stage_checkpoint table."""
    inspector = inspect(database.engine)
    columns = {col["name"]: col["type"] for col in inspector.get_columns("debate_stage_checkpoint")}
    
    expected_fields = {
        "id",
        "debate_id",
        "stage_key",
        "status",
        "input_hash",
        "error_message",
        "started_at",
        "completed_at",
        "execution_metadata",
        "attempt",
        "output_reference",
        "failed_at",
        "error_code",
    }
    
    for field in expected_fields:
        assert field in columns, f"Field '{field}' is missing from debate_stage_checkpoint schema."
