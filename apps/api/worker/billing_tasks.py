"""Scheduled billing reconciliation tasks.

Provides Celery tasks for daily and monthly reconciliation runs.
Each run is idempotent (unique run key per period + run type).
Uses Redis distributed lock to prevent duplicate concurrent executions.
"""

from __future__ import annotations

import logging
import time
import uuid

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

RECONCILIATION_LOCK_TTL = 600  # 10 minutes


def _acquire_reconciliation_lock(run_key: str) -> Optional[object]:
    """Acquire a Redis distributed lock for reconciliation.

    Returns a lock object (or truthy token) if acquired, None if locked.
    """
    try:
        from redis_pool import get_sync_redis_client
        client = get_sync_redis_client()
        if client is None:
            return None
        lock_key = f"lock:billing-reconciliation:{run_key}"
        import os
        owner = f"{os.getpid()}:{uuid.uuid4().hex}"
        acquired = client.set(lock_key, owner, nx=True, ex=RECONCILIATION_LOCK_TTL)
        if acquired:
            return (client, lock_key, owner)
        logger.info("Reconciliation lock already held: run_key=%s", run_key)
        return None
    except Exception as exc:
        logger.warning("Failed to acquire reconciliation lock: %s", exc)
        return None


def _release_reconciliation_lock(lock: object) -> None:
    """Release a Redis distributed lock if we own it."""
    if lock is None:
        return
    try:
        client, lock_key, owner = lock
        current = client.get(lock_key)
        if current and current.decode() == owner:
            client.delete(lock_key)
    except Exception as exc:
        logger.warning("Failed to release reconciliation lock: %s", exc)


@celery_app.task(name="billing.reconcile_previous_day", bind=True, max_retries=3)
def reconcile_previous_day(self):
    """Reconcile the previous calendar day's usage.

    Runs daily at 03:00 UTC. Uses ReconciliationWindow.previous_utc_day()
    for precise single-day coverage.
    """
    from billing.reconciliation import (
        ReconciliationWindow,
        reconcile_usage,
        record_reconciliation_time,
    )
    from core.database import SessionLocal
    from observability.metrics import (
        record_reconciliation_run,
        record_reconciliation_failure,
        record_reconciliation_discrepancy,
    )

    window = ReconciliationWindow.previous_utc_day()
    run_key = window.run_key("daily")

    lock = _acquire_reconciliation_lock(run_key)
    if lock is None:
        logger.info("Skipping daily reconciliation: lock held for run_key=%s", run_key)
        return

    try:
        start = time.monotonic()
        with SessionLocal() as db:
            report = reconcile_usage(db, window=window, run_type="daily")
        elapsed = time.monotonic() - start
        record_reconciliation_run("daily", "completed", elapsed)
        record_reconciliation_time()
        logger.info(
            "Daily reconciliation completed: window=%s duration=%.1fs run_key=%s",
            window.label, elapsed, run_key,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("daily", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Daily reconciliation failed: window=%s error=%s", window.label, exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        _release_reconciliation_lock(lock)


@celery_app.task(name="billing.reconcile_current_period", bind=True, max_retries=3)
def reconcile_current_period(self):
    """Reconcile the current billing period.

    Runs monthly on the 1st at 04:00 UTC. Uses ReconciliationWindow.closed_month()
    for the previous closed month.
    """
    from billing.reconciliation import (
        ReconciliationWindow,
        reconcile_usage,
        record_reconciliation_time,
    )
    from datetime import datetime, timezone, timedelta
    from core.database import SessionLocal
    from observability.metrics import (
        record_reconciliation_run,
        record_reconciliation_failure,
    )

    last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    window = ReconciliationWindow.closed_month(last_month.year, last_month.month)
    run_key = window.run_key("monthly")

    lock = _acquire_reconciliation_lock(run_key)
    if lock is None:
        logger.info("Skipping monthly reconciliation: lock held for run_key=%s", run_key)
        return

    try:
        start = time.monotonic()
        with SessionLocal() as db:
            report = reconcile_usage(db, window=window, run_type="monthly")
        elapsed = time.monotonic() - start
        record_reconciliation_run("monthly", "completed", elapsed)
        record_reconciliation_time()
        logger.info(
            "Monthly reconciliation completed: window=%s duration=%.1fs run_key=%s",
            window.label, elapsed, run_key,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("monthly", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Monthly reconciliation failed: window=%s error=%s", window.label, exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        _release_reconciliation_lock(lock)


@celery_app.task(name="billing.reconcile_closed_period", bind=True, max_retries=3)
def reconcile_closed_period(self, period: str):
    """Reconcile a specific closed period on demand.

    Used by admin trigger for manual reconciliation runs.
    Accepts a YYYY-MM period string for backward compatibility.
    """
    from billing.reconciliation import (
        ReconciliationWindow,
        reconcile_usage,
        record_reconciliation_time,
    )
    from core.database import SessionLocal
    from observability.metrics import (
        record_reconciliation_run,
        record_reconciliation_failure,
    )

    window = ReconciliationWindow.from_period(period)
    run_key = window.run_key("manual")

    lock = _acquire_reconciliation_lock(run_key)
    if lock is None:
        logger.info("Skipping manual reconciliation: lock held for run_key=%s", run_key)
        return

    try:
        start = time.monotonic()
        with SessionLocal() as db:
            report = reconcile_usage(db, window=window, run_type="manual")
        elapsed = time.monotonic() - start
        record_reconciliation_run("manual", "completed", elapsed)
        record_reconciliation_time()
        logger.info(
            "Manual reconciliation completed: window=%s duration=%.1fs run_key=%s",
            window.label, elapsed, run_key,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("manual", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Manual reconciliation failed: window=%s error=%s", window.label, exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        _release_reconciliation_lock(lock)
