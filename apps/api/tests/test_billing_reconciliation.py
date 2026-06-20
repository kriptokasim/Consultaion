"""Tests for billing reconciliation cross-referencing."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from billing.reconciliation import (
    RECONCILIATION_VERSION,
    ReconciliationWindow,
    _check_debate_count,
    _check_orphan_usage,
    _check_per_model_tokens,
    _check_token_mismatch,
)


def test_version_is_set():
    assert RECONCILIATION_VERSION == "v2"


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


def test_reconciliation_window_previous_utc_day():
    window = ReconciliationWindow.previous_utc_day()
    assert window.start_at < window.end_at
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    assert window.label == yesterday
    expected_key = f"daily:{window.start_at.isoformat()}:{window.end_at.isoformat()}:v2"
    assert window.run_key("daily") == expected_key


def test_reconciliation_window_closed_month():
    window = ReconciliationWindow.closed_month(2025, 1)
    assert window.start_at == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert window.end_at == datetime(2025, 2, 1, tzinfo=timezone.utc)


def test_reconciliation_window_month_to_date():
    now = datetime.now(timezone.utc)
    window = ReconciliationWindow.month_to_date()
    assert window.start_at == datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    assert window.start_at < window.end_at
    assert abs((window.end_at - now).total_seconds()) < 5
    assert window.label.endswith("-to-date")


def test_reconciliation_window_period_str():
    window = ReconciliationWindow.closed_month(2025, 6)
    assert window.period_str() == "2025-06"


def test_per_model_token_mismatch_detected():
    db = MagicMock()
    db.exec.return_value.one.return_value = 500  # LLM reports 500 tokens
    window = ReconciliationWindow.closed_month(2025, 6)

    discs = _check_per_model_tokens(db, "user-1", {"gpt-4": 1000}, window)
    assert len(discs) == 1
    assert discs[0]["type"] == "per_model_token_mismatch"


def test_per_model_token_match():
    db = MagicMock()
    db.exec.return_value.one.return_value = 1000  # Exact match
    window = ReconciliationWindow.closed_month(2025, 6)

    discs = _check_per_model_tokens(db, "user-1", {"gpt-4": 1000}, window)
    assert len(discs) == 0


def test_orphan_usage_detected():
    db = MagicMock()
    db.exec.return_value.all.return_value = [("orphan-user", 5)]
    window = ReconciliationWindow.closed_month(2025, 6)

    discs = _check_orphan_usage(db, window)
    assert len(discs) == 1
    assert discs[0]["type"] == "orphan_usage"
    assert discs[0]["user_id"] == "orphan-user"


def test_orphan_usage_none_found():
    db = MagicMock()
    db.exec.return_value.all.return_value = []
    window = ReconciliationWindow.closed_month(2025, 6)

    discs = _check_orphan_usage(db, window)
    assert len(discs) == 0
