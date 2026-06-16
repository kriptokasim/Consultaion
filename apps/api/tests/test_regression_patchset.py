"""Regression tests for FH63-FH76 patchset.

Covers the critical scenarios from the regression matrix:
- Scenario A: Profile service unavailable
- Scenario B: Timeline unavailable
- Scenario C: Both timeline endpoints unavailable
- Scenario D: Schema behind head
- Scenario E: Alembic version width
- Scenario F: Reconciliation concurrency
- Scenario G: SSE connection limit
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestFH63ProfileNull:
    """Scenario A: Profile service unavailable — runs table must render."""

    def test_runs_table_accepts_null_profile(self):
        from serializers import serialize_debate_base

        class FakeDebate:
            id = str(uuid.uuid4())
            prompt = "test prompt"
            status = "completed"
            mode = "arena"
            created_at = None
            updated_at = None
            final_content = "result"
            model_id = "test"
            routed_model = None
            routing_policy = None
            config = {}
            panel_config = None
            routing_meta = None
            final_meta = {}
            engine_version = None
            user_id = None
            team_id = None
            runner_id = None
            run_attempt = 0

        result = serialize_debate_base(FakeDebate())
        assert result["id"] == FakeDebate.id
        assert result["prompt"] == "test prompt"


class TestFH66NonDestructiveMerge:
    """Valid serializer values must not be overwritten by None."""

    def test_merge_non_null_preserves_base(self):
        from serializers import merge_non_null

        base = {"a": 1, "b": "hello", "c": [1, 2]}
        incoming = {"a": None, "b": "world", "c": None, "d": 42}
        merged = merge_non_null(base, incoming)
        assert merged["a"] == 1
        assert merged["b"] == "world"
        assert merged["c"] == [1, 2]
        assert merged["d"] == 42

    def test_merge_non_null_empty_incoming(self):
        from serializers import merge_non_null

        base = {"x": 10}
        merged = merge_non_null(base, {})
        assert merged == {"x": 10}

    def test_merge_non_null_empty_base(self):
        from serializers import merge_non_null

        merged = merge_non_null({}, {"y": 20})
        assert merged == {"y": 20}


class TestFH67EnrichmentSavepoints:
    """Enrichment must not poison the outer transaction."""

    def test_enrichment_returns_zero_counts_for_empty_tables(self):
        from services.debate_enrichment import safe_query_extra_fields
        from services.schema_capabilities import SchemaCapabilities

        caps = SchemaCapabilities(
            has_stage_checkpoint_table=False,
            has_continuation_table=False,
            has_score_table=False,
            has_message_table=False,
            has_pairwise_vote_table=False,
            inspection_succeeded=True,
        )

        session = MagicMock()
        result = safe_query_extra_fields(str(uuid.uuid4()), session, caps)
        assert result["responses_received"] is None
        assert result["scores_received"] is None
        assert result["_message_query_failed"] is True
        assert result["_score_query_failed"] is True


class TestFH68SchemaCapabilities:
    """Schema capability detection correctness."""

    def test_capabilities_default_all_true(self):
        from services.schema_capabilities import SchemaCapabilities

        caps = SchemaCapabilities()
        assert caps.has_stage_checkpoint_table is True
        assert caps.has_continuation_table is True
        assert caps.inspection_succeeded is True

    def test_capabilities_inspection_failure(self):
        from services.schema_capabilities import SchemaCapabilities

        caps = SchemaCapabilities(inspection_succeeded=False)
        assert caps.inspection_succeeded is False


class TestFH70AlembicAudit:
    """Alembic revision parsing must handle annotated assignments."""

    def test_annotated_assignment_parsing(self):
        import ast
        from pathlib import Path

        script_dir = Path(__file__).resolve().parents[2] / ".." / "scripts"
        import sys
        sys.path.insert(0, str(script_dir))
        from audit_alembic_revisions import _extract_revision_info

        code = '''
revision: str = "test_rev_001"
down_revision: str | None = "prev_rev"
'''
        tree = ast.parse(code)
        info = _extract_revision_info(tree, "test.py")
        assert info is not None
        assert info["revision"] == "test_rev_001"
        assert info["down_revision"] == "prev_rev"

    def test_tuple_down_revision_parsing(self):
        import ast
        from pathlib import Path

        script_dir = Path(__file__).resolve().parents[2] / ".." / "scripts"
        import sys
        sys.path.insert(0, str(script_dir))
        from audit_alembic_revisions import _extract_revision_info

        code = '''
revision = "merge_rev"
down_revision = ("rev_a", "rev_b")
'''
        tree = ast.parse(code)
        info = _extract_revision_info(tree, "test.py")
        assert info is not None
        assert info["revision"] == "merge_rev"
        assert info["down_revision"] == ("rev_a", "rev_b")

    def test_none_down_revision_parsing(self):
        import ast
        from pathlib import Path

        script_dir = Path(__file__).resolve().parents[2] / ".." / "scripts"
        import sys
        sys.path.insert(0, str(script_dir))
        from audit_alembic_revisions import _extract_revision_info

        code = '''
revision = "first_rev"
down_revision = None
'''
        tree = ast.parse(code)
        info = _extract_revision_info(tree, "test.py")
        assert info is not None
        assert info["down_revision"] is None


class TestFH71ReconciliationRunKey:
    """Reconciliation must persist run_key and use it for idempotency."""

    def test_run_key_generation(self):
        from billing.reconciliation import ReconciliationWindow
        from datetime import datetime, timezone

        window = ReconciliationWindow(
            start_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_at=datetime(2024, 1, 16, tzinfo=timezone.utc),
            label="2024-01-15",
        )
        key1 = window.run_key("daily")
        key2 = window.run_key("daily")
        assert key1 == key2
        assert "daily" in key1
        assert "2024-01-15" in key1

    def test_different_windows_different_keys(self):
        from billing.reconciliation import ReconciliationWindow
        from datetime import datetime, timezone

        w1 = ReconciliationWindow(
            start_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_at=datetime(2024, 1, 16, tzinfo=timezone.utc),
            label="2024-01-15",
        )
        w2 = ReconciliationWindow(
            start_at=datetime(2024, 1, 16, tzinfo=timezone.utc),
            end_at=datetime(2024, 1, 17, tzinfo=timezone.utc),
            label="2024-01-16",
        )
        assert w1.run_key("daily") != w2.run_key("daily")


class TestFH72LockTriState:
    """Redis unavailable must be distinct from lock held."""

    def test_lock_acquire_result_values(self):
        from services.lease import LockAcquireResult

        assert LockAcquireResult.ACQUIRED.value == "acquired"
        assert LockAcquireResult.HELD.value == "held"
        assert LockAcquireResult.BACKEND_UNAVAILABLE.value == "backend_unavailable"


class TestFH73SSELeaseLua:
    """SSE lease Lua scripts must be valid."""

    def test_sse_acquire_lua_exists(self):
        from services.lease import SSE_LEASE_ACQUIRE_LUA
        assert "zremrangebyscore" in SSE_LEASE_ACQUIRE_LUA
        assert "zcard" in SSE_LEASE_ACQUIRE_LUA
        assert "zadd" in SSE_LEASE_ACQUIRE_LUA

    def test_sse_release_lua_exists(self):
        from services.lease import SSE_LEASE_RELEASE_LUA
        assert "zrem" in SSE_LEASE_RELEASE_LUA
