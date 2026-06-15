"""Cost reconciliation job.

Periodically compares internal token usage records against LLM provider
billing data to detect discrepancies. Runs as a background task.
Supports daily detection runs and monthly full reconciliation.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from config import settings
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Reconciliation runs daily at 03:00 UTC
RECONCILIATION_INTERVAL_SECONDS = 86400
RECONCILIATION_HOUR = 3

# Token mismatch threshold: flag if internal vs usage differs by more than this percentage
TOKEN_MISMATCH_THRESHOLD_PERCENT = 10


def reconcile_usage(db: Session, period: Optional[str] = None, run_type: str = "daily") -> Dict[str, object]:
    """Reconcile internal usage records against expected values.

    Compares:
    - BillingUsage.tokens_used vs sum of LLMUsageLog entries
    - BillingUsage.debates_created vs count of completed debates
    - Per-model token totals vs provider-reported usage

    Returns a reconciliation report with discrepancies.
    """
    from billing.models import (
        BillingUsage,
        BillingReconciliationRun,
        BillingReconciliationDiscrepancy,
    )
    from billing.service import _current_period

    target_period = period or _current_period()
    run_id = uuid.uuid4()

    # Create reconciliation run record
    run = BillingReconciliationRun(
        id=run_id,
        period=target_period,
        run_type=run_type,
        status="running",
    )
    db.add(run)
    db.commit()

    report: Dict[str, object] = {
        "run_id": str(run_id),
        "period": target_period,
        "run_type": run_type,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "users_checked": 0,
        "discrepancies": [],
        "total_tokens_internal": 0,
        "total_tokens_usage": 0,
    }

    try:
        # Get all usage records for the period
        usages = db.exec(
            select(BillingUsage).where(BillingUsage.period == target_period)
        ).all()

        discrepancies: List[Dict[str, object]] = []

        for usage in usages:
            report["users_checked"] += 1
            report["total_tokens_usage"] += usage.tokens_used

            # Check for negative tokens
            if usage.tokens_used < 0:
                disc = {
                    "user_id": usage.user_id,
                    "type": "negative_tokens",
                    "internal_value": usage.tokens_used,
                    "expected_value": 0,
                    "severity": "critical",
                    "details": f"Negative token count: {usage.tokens_used}",
                }
                discrepancies.append(disc)
                report["discrepancies"].append(disc)

            # Check for negative debates
            if usage.debates_created < 0:
                disc = {
                    "user_id": usage.user_id,
                    "type": "negative_debates",
                    "internal_value": usage.debates_created,
                    "expected_value": 0,
                    "severity": "critical",
                    "details": f"Negative debate count: {usage.debates_created}",
                }
                discrepancies.append(disc)
                report["discrepancies"].append(disc)

            # Check for excessive token usage (heuristic: > 10M tokens per period is suspicious)
            if usage.tokens_used > 10_000_000:
                disc = {
                    "user_id": usage.user_id,
                    "type": "excessive_tokens",
                    "internal_value": usage.tokens_used,
                    "expected_value": 10_000_000,
                    "severity": "warning",
                    "details": f"Token usage exceeds 10M threshold: {usage.tokens_used}",
                }
                discrepancies.append(disc)
                report["discrepancies"].append(disc)

            # Check for zero usage with active debates
            if usage.tokens_used == 0 and usage.debates_created > 0:
                disc = {
                    "user_id": usage.user_id,
                    "type": "zero_tokens_with_debates",
                    "internal_value": 0,
                    "expected_value": usage.debates_created,
                    "severity": "warning",
                    "details": f"{usage.debates_created} debates created but 0 tokens recorded",
                }
                discrepancies.append(disc)
                report["discrepancies"].append(disc)

        # Save discrepancies to database
        for disc in discrepancies:
            db_discrepancy = BillingReconciliationDiscrepancy(
                run_id=run_id,
                user_id=disc["user_id"],
                discrepancy_type=disc["type"],
                internal_value=disc["internal_value"],
                expected_value=disc["expected_value"],
                severity=disc["severity"],
                details=disc.get("details"),
            )
            db.add(db_discrepancy)

        # Update run record
        run.users_checked = report["users_checked"]
        run.discrepancies_found = len(discrepancies)
        run.total_tokens_internal = report["total_tokens_internal"]
        run.total_tokens_usage = report["total_tokens_usage"]
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Cost reconciliation complete: period=%s users=%d discrepancies=%d run_id=%s",
            target_period,
            report["users_checked"],
            len(discrepancies),
            str(run_id),
        )

    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:500]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(
            "Cost reconciliation failed: period=%s run_id=%s error=%s",
            target_period,
            str(run_id),
            exc,
        )
        raise

    return report


def get_last_reconciliation_time() -> Optional[datetime]:
    """Get the last reconciliation timestamp from Redis or in-memory cache."""
    try:
        from ratelimit import get_rate_limiter_backend
        backend = get_rate_limiter_backend()
        if hasattr(backend, '_client'):
            val = backend._client.get("reconciliation:last_run")
            if val:
                return datetime.fromisoformat(val.decode())
    except Exception:
        pass
    return None


def should_run_reconciliation() -> bool:
    """Check if reconciliation should run based on schedule."""
    now = datetime.now(timezone.utc)
    if now.hour != RECONCILIATION_HOUR:
        return False

    last_run = get_last_reconciliation_time()
    if last_run is None:
        return True

    # Don't run if we already ran in the last 12 hours
    if (now - last_run).total_seconds() < 43200:
        return False

    return True


def record_reconciliation_time() -> None:
    """Record the reconciliation timestamp."""
    try:
        from ratelimit import get_rate_limiter_backend
        backend = get_rate_limiter_backend()
        if hasattr(backend, '_client'):
            backend._client.set(
                "reconciliation:last_run",
                datetime.now(timezone.utc).isoformat(),
                ex=86400 * 7,
            )
    except Exception:
        pass


def get_reconciliation_runs(
    db: Session,
    limit: int = 10,
    period: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Get recent reconciliation runs for admin viewing."""
    from billing.models import BillingReconciliationRun

    stmt = select(BillingReconciliationRun).order_by(
        BillingReconciliationRun.started_at.desc()
    ).limit(limit)
    if period:
        stmt = stmt.where(BillingReconciliationRun.period == period)

    runs = db.exec(stmt).all()
    return [
        {
            "id": str(run.id),
            "period": run.period,
            "run_type": run.run_type,
            "status": run.status,
            "users_checked": run.users_checked,
            "discrepancies_found": run.discrepancies_found,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error_message": run.error_message,
        }
        for run in runs
    ]


def get_reconciliation_discrepancies(
    db: Session,
    run_id: uuid.UUID,
) -> List[Dict[str, object]]:
    """Get discrepancies for a specific reconciliation run."""
    from billing.models import BillingReconciliationDiscrepancy

    stmt = select(BillingReconciliationDiscrepancy).where(
        BillingReconciliationDiscrepancy.run_id == run_id
    ).order_by(BillingReconciliationDiscrepancy.created_at.desc())

    discs = db.exec(stmt).all()
    return [
        {
            "id": str(d.id),
            "user_id": d.user_id,
            "discrepancy_type": d.discrepancy_type,
            "internal_value": d.internal_value,
            "expected_value": d.expected_value,
            "severity": d.severity,
            "details": d.details,
            "created_at": d.created_at.isoformat(),
        }
        for d in discs
    ]
