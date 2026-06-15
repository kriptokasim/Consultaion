"""Tests for billing reconciliation cross-referencing."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid

from billing.reconciliation import (
    _check_token_mismatch,
    _check_debate_count,
    _check_per_model_tokens,
    _check_orphan_usage,
    _check_cost_reconciliation,
    _period_start,
    _period_end,
    RECONCILIATION_VERSION,
    RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE,
)


def test_version_is_set():
    assert RECONCILIATION_VERSION == "v1"


def test_token_mismatch_within_tolerance():
    disc = _check_token_mismatch("user-1", 1000, 1050)
    assert disc is None  # 50 < 100 tolerance


def test_token_mismatch_exceeds_tolerance():
    disc = _check_token_mismatch("user-1", 1000, 3000)
    assert disc is not None
    assert disc["type"] == "token_mismatch"
    assert disc["severity"] == "critical"


def test_debate_count_mismatch_within_tolerance():
    disc = _check_debate_count("user-1", 50, 51)
    assert disc is None  # 2% diff <= 2% tolerance


def test_debate_count_mismatch_exceeds_tolerance():
    disc = _check_debate_count("user-1", 50, 60)
    assert disc is not None
    assert disc["type"] == "debate_count_mismatch"


def test_period_start_parsing():
    assert _period_start("2025-01") == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert _period_start("2025-12") == datetime(2025, 12, 1, tzinfo=timezone.utc)


def test_period_end_parsing():
    assert _period_end("2025-01") == datetime(2025, 2, 1, tzinfo=timezone.utc)
    assert _period_end("2025-12") == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_per_model_token_mismatch_detected():
    db = MagicMock()
    db.exec.return_value.one.return_value = 500  # LLM reports 500 tokens

    discs = _check_per_model_tokens(db, "user-1", {"gpt-4": 1000}, "2025-06")
    assert len(discs) == 1
    assert discs[0]["type"] == "per_model_token_mismatch"


def test_per_model_token_match():
    db = MagicMock()
    db.exec.return_value.one.return_value = 1000  # Exact match

    discs = _check_per_model_tokens(db, "user-1", {"gpt-4": 1000}, "2025-06")
    assert len(discs) == 0


def test_orphan_usage_detected():
    db = MagicMock()
    db.exec.return_value.all.return_value = [("orphan-user", 5)]

    discs = _check_orphan_usage(db, "2025-06")
    assert len(discs) == 1
    assert discs[0]["type"] == "orphan_usage"
    assert discs[0]["user_id"] == "orphan-user"


def test_orphan_usage_none_found():
    db = MagicMock()
    db.exec.return_value.all.return_value = []

    discs = _check_orphan_usage(db, "2025-06")
    assert len(discs) == 0
