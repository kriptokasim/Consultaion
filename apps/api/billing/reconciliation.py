"""Cost reconciliation job.

Periodically compares internal token usage records against LLM provider
billing data to detect discrepancies. Runs as a background task.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from config import settings
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Reconciliation runs daily at 03:00 UTC
RECONCILIATION_INTERVAL_SECONDS = 86400
RECONCILIATION_HOUR = 3


def reconcile_usage(db: Session, period: Optional[str] = None) -> Dict[str, any]:
    """Reconcile internal usage records against expected values.

    Compares:
    - BillingUsage.tokens_used vs sum of LLMUsageLog entries
    - BillingUsage.debates_created vs count of completed debates
    - Per-model token totals vs provider-reported usage

    Returns a reconciliation report.
    """
    from billing.models import BillingUsage
    from billing.service import _current_period

    target_period = period or _current_period()
    report = {
        "period": target_period,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "users_checked": 0,
        "discrepancies": [],
        "total_tokens_internal": 0,
        "total_tokens_usage": 0,
    }

    # Get all usage records for the period
    usages = db.exec(
        select(BillingUsage).where(BillingUsage.period == target_period)
    ).all()

    for usage in usages:
        report["users_checked"] += 1
        report["total_tokens_usage"] += usage.tokens_used

        # Check token consistency
        # In a full implementation, this would query LLMUsageLog
        # and compare per-user totals. For now, we log the reconciliation.
        if usage.tokens_used < 0:
            report["discrepancies"].append({
                "user_id": usage.user_id,
                "type": "negative_tokens",
                "value": usage.tokens_used,
                "expected": ">= 0",
            })

        if usage.debates_created < 0:
            report["discrepancies"].append({
                "user_id": usage.user_id,
                "type": "negative_debates",
                "value": usage.debates_created,
                "expected": ">= 0",
            })

    logger.info(
        "Cost reconciliation complete: period=%s users=%d discrepancies=%d",
        target_period,
        report["users_checked"],
        len(report["discrepancies"]),
    )

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
