"""Tests for render schema diagnostic script to catch drift."""

import importlib.util
import os
import sys
from pathlib import Path

from sqlmodel import Session

# Import script safely
BASE_DIR = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = BASE_DIR / "scripts"

spec = importlib.util.spec_from_file_location(
    "render_schema_diagnostic", str(SCRIPTS_DIR / "render-schema-diagnostic.py")
)
render_schema_diagnostic = importlib.util.module_from_spec(spec)
sys.modules["render_schema_diagnostic"] = render_schema_diagnostic
spec.loader.exec_module(render_schema_diagnostic)


def test_diagnose_debate_returns_dict(db_session: Session):
    """Verify diagnose_debate runs safely and returns expected structure."""
    result = render_schema_diagnostic.diagnose_debate(db_session, "fake-debate-id")
    assert isinstance(result, dict)
    assert result["debate_id"] == "fake-debate-id"
    assert "message_table_exists" in result
    assert "continuation_count" in result
    assert "has_synthesis_report" in result


def test_verify_critical_columns_covers_debate_continuation(db_session: Session):
    """Ensure verify_critical_columns checks the new debate_continuation schema."""
    from services.migration_safety import MODEL_CRITICAL_COLUMNS, verify_critical_columns

    assert "debate_continuation" in MODEL_CRITICAL_COLUMNS

    required_cols = set(MODEL_CRITICAL_COLUMNS["debate_continuation"])
    expected_new_cols = {
        "cancelled_at",
        "paused_at",
        "failure_code",
        "failure_detail_safe",
        "credit_reservation_id",
        "retry_of_continuation_id",
    }
    
    assert expected_new_cols.issubset(required_cols), "New schema drift columns missing from config"

    # Execute the actual verify function against the active db_session
    missing = verify_critical_columns(db_session)
    missing_continuation_cols = [c for c in missing if c.startswith("debate_continuation.")]
    assert not missing_continuation_cols, f"Found schema drift in test database: {missing_continuation_cols}"
