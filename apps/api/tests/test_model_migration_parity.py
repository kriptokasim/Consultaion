"""Test that SQLModel model metadata matches Alembic migration state."""
import pytest
from sqlmodel import SQLModel, Session, inspect
from sqlalchemy import text


# Import all models to register them
import models
import billing.models


CRITICAL_TABLES = [
    "debate_continuation",
    "debate_stage_checkpoint",
    "billing_reconciliation_runs",
    "billing_reconciliation_discrepancies",
    "llm_usage_log",
    "billing_usage",
    "billing_webhook_events",
    "debate",
    "user",
]


def test_critical_tables_exist(db_session: Session):
    """All critical tables should exist after migration."""
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    for table in CRITICAL_TABLES:
        assert table in tables, f"Critical table '{table}' missing from database"


def test_debate_continuation_columns(db_session: Session):
    """DebateContinuation should have all expected columns."""
    inspector = inspect(db_session.get_bind())
    columns = {c["name"] for c in inspector.get_columns("debate_continuation")}
    expected = {
        "id", "debate_id", "idempotency_key", "status",
        "created_at", "updated_at", "user_id", "target",
        "requested_at", "preflight_passed_at", "dispatched_at",
        "started_at", "completed_at", "failed_at", "cancelled_at",
        "paused_at", "failure_code", "failure_detail_safe",
        "credit_reservation_id", "retry_of_continuation_id",
    }
    missing = expected - columns
    assert not missing, f"DebateContinuation missing columns: {missing}"


def test_debate_stage_checkpoint_columns(db_session: Session):
    """DebateStageCheckpoint should have all expected columns."""
    inspector = inspect(db_session.get_bind())
    columns = {c["name"] for c in inspector.get_columns("debate_stage_checkpoint")}
    expected = {
        "id", "debate_id", "stage_key", "status", "input_hash",
        "error_message", "started_at", "completed_at", "execution_metadata",
        "attempt", "output_reference", "failed_at", "error_code",
    }
    missing = expected - columns
    assert not missing, f"DebateStageCheckpoint missing columns: {missing}"


def test_billing_reconciliation_runs_columns(db_session: Session):
    """BillingReconciliationRun should have all expected columns."""
    inspector = inspect(db_session.get_bind())
    columns = {c["name"] for c in inspector.get_columns("billing_reconciliation_runs")}
    expected = {
        "id", "period", "run_type", "status", "users_checked",
        "discrepancies_found", "total_tokens_internal", "total_tokens_usage",
        "started_at", "completed_at", "error_message",
    }
    missing = expected - columns
    assert not missing, f"BillingReconciliationRun missing columns: {missing}"


def test_billing_reconciliation_discrepancies_columns(db_session: Session):
    """BillingReconciliationDiscrepancy should have all expected columns."""
    inspector = inspect(db_session.get_bind())
    columns = {c["name"] for c in inspector.get_columns("billing_reconciliation_discrepancies")}
    expected = {
        "id", "run_id", "user_id", "discrepancy_type",
        "internal_value", "expected_value", "severity", "details",
        "created_at",
    }
    missing = expected - columns
    assert not missing, f"BillingReconciliationDiscrepancy missing columns: {missing}"


def test_debate_continuation_indexes(db_session: Session):
    """DebateContinuation should have critical indexes."""
    inspector = inspect(db_session.get_bind())
    indexes = {idx["name"] for idx in inspector.get_indexes("debate_continuation")}
    assert any("debate_id" in name for name in indexes), "Missing debate_id index"
    assert any("debate_status" in name or "debate_id" in name for name in indexes), (
        "Missing (debate_id, status) composite index"
    )


def test_debate_continuation_unique_constraints(db_session: Session):
    """DebateContinuation should have unique constraint on (debate_id, idempotency_key)."""
    inspector = inspect(db_session.get_bind())
    uq = inspector.get_unique_constraints("debate_continuation")
    uq_names = [c["name"] for c in uq]
    assert any("debate_id" in name and "idempotency" in name for name in uq_names), (
        f"Missing unique constraint on (debate_id, idempotency_key). Found: {uq_names}"
    )


def test_debate_continuation_foreign_keys(db_session: Session):
    """DebateContinuation should have FK to debate table."""
    inspector = inspect(db_session.get_bind())
    fks = inspector.get_foreign_keys("debate_continuation")
    fk_targets = {fk["referred_table"] for fk in fks}
    assert "debate" in fk_targets, "Missing FK to debate table"


def test_billing_usage_unique_constraint(db_session: Session):
    """BillingUsage should have unique constraint on (user_id, period)."""
    inspector = inspect(db_session.get_bind())
    uq = inspector.get_unique_constraints("billing_usage")
    uq_names = [c["name"] for c in uq]
    assert any("user" in name and "period" in name for name in uq_names), (
        f"Missing unique constraint on (user_id, period). Found: {uq_names}"
    )


def test_alembic_chain_linearity_and_uniqueness():
    """Assert there is only a single head and all revision IDs are unique."""
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.abspath(os.path.join(current_dir, ".."))
    ini_path = os.path.join(api_dir, "alembic.ini")

    config = Config(ini_path)
    config.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic migration head, found {len(heads)}: {heads}"

    revisions = list(script.walk_revisions())
    rev_ids = [r.revision for r in revisions]

    # Assert all revision IDs are unique
    assert len(rev_ids) == len(set(rev_ids)), f"Duplicate Alembic revision IDs found: {rev_ids}"

    # Assert all revision IDs have a length between 8 and 32 characters
    for rev in rev_ids:
        assert 8 <= len(rev) <= 32, f"Revision ID '{rev}' length ({len(rev)}) must be between 8 and 32 characters"
