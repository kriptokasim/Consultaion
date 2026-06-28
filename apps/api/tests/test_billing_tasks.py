"""Tests for worker.billing_tasks reconciliation tasks.

Validates reconcile_previous_day, reconcile_current_period, and
reconcile_closed_period including distributed lock behavior, retry
on Redis unavailability, and lock release in finally blocks.

We call the inner function body directly via the task's __call__
to avoid Celery broker/backend teardown issues in test environments.
"""
from unittest.mock import MagicMock, patch

import pytest
from worker.billing_tasks import (
    LockAcquireResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reconciliation_module_patches():
    """Provide patches for all lazy-imported modules inside billing tasks."""
    mock_window = MagicMock()
    mock_window.label = "2026-06-17"
    mock_window.run_key.return_value = "test:2026-06-17"

    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_ctx.__exit__ = MagicMock(return_value=False)

    return {
        "billing.reconciliation": MagicMock(
            ReconciliationWindow=MagicMock(
                previous_utc_day=MagicMock(return_value=mock_window),
                closed_month=MagicMock(return_value=mock_window),
                from_period=MagicMock(return_value=mock_window),
            ),
            reconcile_usage=MagicMock(return_value={"status": "ok"}),
            record_reconciliation_time=MagicMock(),
        ),
        "database": MagicMock(
            SessionLocal=MagicMock(return_value=mock_session_ctx),
        ),
        "observability.metrics": MagicMock(
            record_reconciliation_run=MagicMock(),
            record_reconciliation_failure=MagicMock(),
            record_reconciliation_discrepancy=MagicMock(),
        ),
    }


# ---------------------------------------------------------------------------
# Import the raw function bodies directly, bypassing Celery task wrapping
# ---------------------------------------------------------------------------

# The billing_tasks module decorates functions with @celery_app.task(bind=True).
# In test env without a real Celery broker, we import the module and access the
# underlying callable. With the EagerTask wrapper, __call__ invokes func(self, ...).

from worker.billing_tasks import (
    reconcile_closed_period as _manual_task,
    reconcile_current_period as _monthly_task,
    reconcile_previous_day as _daily_task,
)

# ---------------------------------------------------------------------------
# Lock behavior tests
# ---------------------------------------------------------------------------

class TestLockBehavior:
    @patch("worker.billing_tasks._acquire_reconciliation_lock",
           return_value=(LockAcquireResult.HELD, None))
    def test_lock_already_held_skips_daily(self, _mock_lock):
        """When lock is already held, daily task returns without processing."""
        with patch.dict("sys.modules", _reconciliation_module_patches()):
            # Calling the task directly — EagerTask.__call__ passes self for bind=True
            result = _daily_task()
        # Should return None (early exit)
        assert result is None

    @patch("worker.billing_tasks._acquire_reconciliation_lock",
           return_value=(LockAcquireResult.HELD, None))
    def test_lock_already_held_skips_monthly(self, _mock_lock):
        """Monthly reconciliation skips when lock is held."""
        with patch.dict("sys.modules", _reconciliation_module_patches()):
            result = _monthly_task()
        assert result is None

    @patch("worker.billing_tasks._acquire_reconciliation_lock",
           return_value=(LockAcquireResult.HELD, None))
    def test_lock_already_held_skips_manual(self, _mock_lock):
        """Manual reconciliation skips when lock is held."""
        with patch.dict("sys.modules", _reconciliation_module_patches()):
            result = _manual_task("2026-05")
        assert result is None


class TestRedisUnavailableRetry:
    @patch("worker.billing_tasks._acquire_reconciliation_lock",
           return_value=(LockAcquireResult.BACKEND_UNAVAILABLE, None))
    def test_daily_retries_on_redis_unavailable(self, _mock_lock):
        """Daily reconciliation retries when Redis is unavailable."""
        with patch.dict("sys.modules", _reconciliation_module_patches()):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                _daily_task()

    @patch("worker.billing_tasks._acquire_reconciliation_lock",
           return_value=(LockAcquireResult.BACKEND_UNAVAILABLE, None))
    def test_manual_retries_on_redis_unavailable(self, _mock_lock):
        """Manual reconciliation retries when Redis is unavailable."""
        with patch.dict("sys.modules", _reconciliation_module_patches()):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                _manual_task("2026-05")


class TestSuccessfulReconciliation:
    @patch("worker.billing_tasks._release_reconciliation_lock")
    @patch("worker.billing_tasks._renew_lock", return_value=True)
    @patch("worker.billing_tasks._acquire_reconciliation_lock")
    def test_daily_acquires_runs_and_releases(self, mock_acquire, _mock_renew, mock_release):
        """Successful daily reconciliation acquires lock, runs, and releases."""
        mock_lock_info = (MagicMock(), "lock:key", "owner-id")
        mock_acquire.return_value = (LockAcquireResult.ACQUIRED, mock_lock_info)

        with patch.dict("sys.modules", _reconciliation_module_patches()):
            _daily_task()

        mock_release.assert_called_once_with(mock_lock_info)


class TestFailureReleasesLock:
    @patch("worker.billing_tasks._release_reconciliation_lock")
    @patch("worker.billing_tasks._renew_lock", return_value=True)
    @patch("worker.billing_tasks._acquire_reconciliation_lock")
    def test_failure_still_releases_lock(self, mock_acquire, _mock_renew, mock_release):
        """On reconciliation failure, lock is still released in finally."""
        mock_lock_info = (MagicMock(), "lock:key", "owner-id")
        mock_acquire.return_value = (LockAcquireResult.ACQUIRED, mock_lock_info)

        patches = _reconciliation_module_patches()
        patches["billing.reconciliation"].reconcile_usage.side_effect = RuntimeError("DB error")

        with patch.dict("sys.modules", patches):
            with pytest.raises((RuntimeError, Exception)):
                _daily_task()

        # Lock must be released even on failure
        mock_release.assert_called_once_with(mock_lock_info)
