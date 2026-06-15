"""Scheduled billing reconciliation tasks.

Provides Celery tasks for daily and monthly reconciliation runs.
Each run is idempotent (unique run key per period + run type).
"""

from __future__ import annotations

import logging
import time

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="billing.reconcile_previous_day", bind=True, max_retries=3)
def reconcile_previous_day(self):
    """Reconcile the previous calendar day's usage.

    Runs daily at 03:00 UTC. Cross-references BillingUsage against
    LLMUsageLog for the previous day.
    """
    from billing.reconciliation import reconcile_usage, record_reconciliation_time
    from datetime import datetime, timezone, timedelta
    from core.database import SessionLocal
    from observability.metrics import record_reconciliation_run, record_reconciliation_failure, record_reconciliation_discrepancy

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    period = yesterday.strftime("%Y-%m")

    start = time.monotonic()
    try:
        with SessionLocal() as db:
            report = reconcile_usage(db, period=period, run_type="daily")
        elapsed = time.monotonic() - start
        record_reconciliation_run("daily", "completed", elapsed)
        record_reconciliation_time()
        logger.info("Daily reconciliation completed: period=%s duration=%.1fs", period, elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("daily", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Daily reconciliation failed: period=%s error=%s", period, exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="billing.reconcile_current_period", bind=True, max_retries=3)
def reconcile_current_period(self):
    """Reconcile the current billing period.

    Runs monthly on the 1st at 04:00 UTC. Full cross-reference
    of all usage for the previous month.
    """
    from billing.reconciliation import reconcile_usage, record_reconciliation_time
    from datetime import datetime, timezone
    from core.database import SessionLocal
    from observability.metrics import record_reconciliation_run, record_reconciliation_failure

    last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    period = last_month.strftime("%Y-%m")

    start = time.monotonic()
    try:
        with SessionLocal() as db:
            report = reconcile_usage(db, period=period, run_type="monthly")
        elapsed = time.monotonic() - start
        record_reconciliation_run("monthly", "completed", elapsed)
        record_reconciliation_time()
        logger.info("Monthly reconciliation completed: period=%s duration=%.1fs", period, elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("monthly", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Monthly reconciliation failed: period=%s error=%s", period, exc)
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(name="billing.reconcile_closed_period", bind=True, max_retries=3)
def reconcile_closed_period(self, period: str):
    """Reconcile a specific closed period on demand.

    Used by admin trigger for manual reconciliation runs.
    """
    from billing.reconciliation import reconcile_usage, record_reconciliation_time
    from core.database import SessionLocal
    from observability.metrics import record_reconciliation_run, record_reconciliation_failure

    start = time.monotonic()
    try:
        with SessionLocal() as db:
            report = reconcile_usage(db, period=period, run_type="manual")
        elapsed = time.monotonic() - start
        record_reconciliation_run("manual", "completed", elapsed)
        record_reconciliation_time()
        logger.info("Manual reconciliation completed: period=%s duration=%.1fs", period, elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - start
        record_reconciliation_run("manual", "failed", elapsed)
        record_reconciliation_failure(type(exc).__name__)
        logger.error("Manual reconciliation failed: period=%s error=%s", period, exc)
        raise self.retry(exc=exc, countdown=300)
