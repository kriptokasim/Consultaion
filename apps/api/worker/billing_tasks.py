"""Scheduled billing reconciliation tasks.

Provides Celery tasks for daily and monthly reconciliation runs.
Each run is idempotent (unique run key per period + run type).
Uses Redis distributed lock to prevent duplicate concurrent executions.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from enum import Enum

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

RECONCILIATION_LOCK_TTL = 600  # 10 minutes
RECONCILIATION_LOCK_RENEW_INTERVAL = 120  # renew every 2 minutes

# Lua script for atomic compare-and-delete release
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""

# Lua script for atomic compare-and-expire renewal
_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("expire", KEYS[1], ARGV[2])
end
return 0
"""

class LockAcquireResult(Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    BACKEND_UNAVAILABLE = "backend_unavailable"


def _acquire_reconciliation_lock(run_key: str) -> tuple[LockAcquireResult, object | None]:
    """Acquire a Redis distributed lock for reconciliation.

    Returns (ACQUIRED, lock_info) if acquired, (HELD, None) if already held,
    or (BACKEND_UNAVAILABLE, None) if Redis is unavailable.
    """
    try:
        from redis_pool import get_sync_redis_client
        client = get_sync_redis_client()
        if client is None:
            return (LockAcquireResult.BACKEND_UNAVAILABLE, None)
        lock_key = f"lock:billing-reconciliation:{run_key}"
        owner = f"{os.getpid()}:{uuid.uuid4().hex}"
        acquired = client.set(lock_key, owner, nx=True, ex=RECONCILIATION_LOCK_TTL)
        if acquired:
            return (LockAcquireResult.ACQUIRED, (client, lock_key, owner))
        logger.info("Reconciliation lock already held: run_key=%s", run_key)
        return (LockAcquireResult.HELD, None)
    except Exception as exc:
        logger.warning("Failed to acquire reconciliation lock: %s", exc)
        return (LockAcquireResult.BACKEND_UNAVAILABLE, None)


def _release_reconciliation_lock(lock: object) -> None:
    """Release a Redis distributed lock atomically if we own it."""
    if lock is None:
        return
    try:
        client, lock_key, owner = lock
        client.eval(_RELEASE_LUA, 1, lock_key, owner)
    except Exception as exc:
        logger.warning("Failed to release reconciliation lock: %s", exc)


def _renew_lock(lock: object) -> bool:
    """Renew a Redis distributed lock atomically if we still own it."""
    if lock is None:
        return False
    try:
        client, lock_key, owner = lock
        result = client.eval(_RENEW_LUA, 1, lock_key, owner, RECONCILIATION_LOCK_TTL)
        return bool(result)
    except Exception as exc:
        logger.warning("Failed to renew reconciliation lock: %s", exc)
        return False


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
    from database import SessionLocal
    from observability.metrics import (
        record_reconciliation_failure,
        record_reconciliation_run,
    )

    window = ReconciliationWindow.previous_utc_day()
    run_key = window.run_key("daily")

    lock_result, lock = _acquire_reconciliation_lock(run_key)
    if lock_result == LockAcquireResult.HELD:
        logger.info("Skipping daily reconciliation: lock held for run_key=%s", run_key)
        return
    if lock_result == LockAcquireResult.BACKEND_UNAVAILABLE:
        logger.error("Daily reconciliation: Redis unavailable for run_key=%s — retrying", run_key)
        raise self.retry(exc=RuntimeError("Redis unavailable"), countdown=60)

    stop_renew = threading.Event()
    def renewer():
        while not stop_renew.wait(RECONCILIATION_LOCK_RENEW_INTERVAL):
            _renew_lock(lock)
            
    renew_thread = threading.Thread(target=renewer, daemon=True)
    renew_thread.start()

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
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        stop_renew.set()
        renew_thread.join(timeout=1.0)
        _release_reconciliation_lock(lock)


@celery_app.task(name="billing.reconcile_current_period", bind=True, max_retries=3)
def reconcile_current_period(self):
    """Reconcile the current billing period.

    Runs monthly on the 1st at 04:00 UTC. Uses ReconciliationWindow.closed_month()
    for the previous closed month.
    """
    from datetime import datetime, timedelta, timezone

    from billing.reconciliation import (
        ReconciliationWindow,
        reconcile_usage,
        record_reconciliation_time,
    )
    from database import SessionLocal
    from observability.metrics import (
        record_reconciliation_failure,
        record_reconciliation_run,
    )

    last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    window = ReconciliationWindow.closed_month(last_month.year, last_month.month)
    run_key = window.run_key("monthly")

    lock_result, lock = _acquire_reconciliation_lock(run_key)
    if lock_result == LockAcquireResult.HELD:
        logger.info("Skipping monthly reconciliation: lock held for run_key=%s", run_key)
        return
    if lock_result == LockAcquireResult.BACKEND_UNAVAILABLE:
        logger.error("Monthly reconciliation: Redis unavailable for run_key=%s — retrying", run_key)
        raise self.retry(exc=RuntimeError("Redis unavailable"), countdown=60)

    stop_renew = threading.Event()
    def renewer():
        while not stop_renew.wait(RECONCILIATION_LOCK_RENEW_INTERVAL):
            _renew_lock(lock)
            
    renew_thread = threading.Thread(target=renewer, daemon=True)
    renew_thread.start()

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
        raise self.retry(exc=exc, countdown=600) from exc
    finally:
        stop_renew.set()
        renew_thread.join(timeout=1.0)
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
    from database import SessionLocal
    from observability.metrics import (
        record_reconciliation_failure,
        record_reconciliation_run,
    )

    window = ReconciliationWindow.from_period(period)
    run_key = window.run_key("manual")

    lock_result, lock = _acquire_reconciliation_lock(run_key)
    if lock_result == LockAcquireResult.HELD:
        logger.info("Skipping manual reconciliation: lock held for run_key=%s", run_key)
        return
    if lock_result == LockAcquireResult.BACKEND_UNAVAILABLE:
        logger.error("Manual reconciliation: Redis unavailable for run_key=%s — retrying", run_key)
        raise self.retry(exc=RuntimeError("Redis unavailable"), countdown=60)

    stop_renew = threading.Event()
    def renewer():
        while not stop_renew.wait(RECONCILIATION_LOCK_RENEW_INTERVAL):
            _renew_lock(lock)
            
    renew_thread = threading.Thread(target=renewer, daemon=True)
    renew_thread.start()

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
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        stop_renew.set()
        renew_thread.join(timeout=1.0)
        _release_reconciliation_lock(lock)
