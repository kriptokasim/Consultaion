"""Cost reconciliation job.

Cross-references BillingUsage against LLMUsageLog to detect real discrepancies
in token counts, per-model usage, debate counts, hosted credits, and orphans.
Runs as a background task. Supports daily detection runs and monthly full reconciliation.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from config import settings
from sqlmodel import Session, select, func, col

logger = logging.getLogger(__name__)

RECONCILIATION_VERSION = "v1"
RECONCILIATION_INTERVAL_SECONDS = 86400
RECONCILIATION_HOUR = 3

# Tolerance thresholds
RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE = 100
RECONCILIATION_TOKEN_TOLERANCE_PERCENT = 5.0
RECONCILIATION_COST_TOLERANCE_USD = 1.0
RECONCILIATION_COST_TOLERANCE_PERCENT = 10.0
RECONCILIATION_DEBATE_TOLERANCE_PERCENT = 2.0


def reconcile_usage(db: Session, period: Optional[str] = None, run_type: str = "daily") -> Dict[str, object]:
    """Cross-reference BillingUsage against LLMUsageLog for real discrepancies."""
    from billing.models import (
        BillingUsage,
        BillingReconciliationRun,
        BillingReconciliationDiscrepancy,
    )
    from billing.service import _current_period
    from models import LLMUsageLog, Debate

    target_period = period or _current_period()
    run_id = uuid.uuid4()

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
        "version": RECONCILIATION_VERSION,
        "period": target_period,
        "run_type": run_type,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "users_checked": 0,
        "discrepancies": [],
        "total_tokens_internal": 0,
        "total_tokens_usage": 0,
    }

    try:
        usages = db.exec(
            select(BillingUsage).where(BillingUsage.period == target_period)
        ).all()

        discrepancies: List[Dict[str, object]] = []

        for usage in usages:
            report["users_checked"] += 1
            report["total_tokens_usage"] += usage.tokens_used

            # 1. Token reconciliation: BillingUsage.tokens_used vs SUM(LLMUsageLog.total_tokens)
            llm_tokens = db.exec(
                select(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                .where(LLMUsageLog.user_id == usage.user_id)
                .where(LLMUsageLog.created_at >= _period_start(target_period))
                .where(LLMUsageLog.created_at < _period_end(target_period))
            ).one()
            report["total_tokens_internal"] += llm_tokens

            disc = _check_token_mismatch(usage.user_id, usage.tokens_used, llm_tokens)
            if disc:
                discrepancies.append(disc)

            # 2. Per-model reconciliation: BillingUsage.model_tokens vs grouped LLMUsageLog
            if usage.model_tokens:
                per_model_discs = _check_per_model_tokens(
                    db, usage.user_id, usage.model_tokens, target_period
                )
                discrepancies.extend(per_model_discs)

            # 3. Debate reconciliation: BillingUsage.debates_created vs completed debates
            completed_debates = db.exec(
                select(func.coalesce(func.count(), 0))
                .where(Debate.user_id == usage.user_id)
                .where(Debate.created_at >= _period_start(target_period))
                .where(Debate.created_at < _period_end(target_period))
            ).one()

            disc = _check_debate_count(usage.user_id, usage.debates_created, completed_debates)
            if disc:
                discrepancies.append(disc)

            # 4. Negative values checks
            for field_name, field_val in [("tokens_used", usage.tokens_used), ("debates_created", usage.debates_created)]:
                if field_val < 0:
                    discrepancies.append({
                        "user_id": usage.user_id,
                        "type": f"negative_{field_name}",
                        "internal_value": field_val,
                        "expected_value": 0,
                        "severity": "critical",
                        "details": f"Negative {field_name}: {field_val}",
                    })

            # 5. Zero tokens with debates
            if usage.tokens_used == 0 and usage.debates_created > 0:
                discrepancies.append({
                    "user_id": usage.user_id,
                    "type": "zero_tokens_with_debates",
                    "internal_value": 0,
                    "expected_value": usage.debates_created,
                    "severity": "warning",
                    "details": f"{usage.debates_created} debates but 0 tokens",
                })

        # 6. Orphan check: LLM usage without a BillingUsage record
        orphan_discs = _check_orphan_usage(db, target_period)
        discrepancies.extend(orphan_discs)

        # 7. Cost reconciliation: total cost_usd vs internal
        cost_discs = _check_cost_reconciliation(db, target_period)
        discrepancies.extend(cost_discs)

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

        run.users_checked = report["users_checked"]
        run.discrepancies_found = len(discrepancies)
        run.total_tokens_internal = report["total_tokens_internal"]
        run.total_tokens_usage = report["total_tokens_usage"]
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Reconciliation complete: period=%s users=%d discrepancies=%d run_id=%s version=%s",
            target_period,
            report["users_checked"],
            len(discrepancies),
            str(run_id),
            RECONCILIATION_VERSION,
        )

    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:500]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(
            "Reconciliation failed: period=%s run_id=%s error=%s",
            target_period,
            str(run_id),
            exc,
        )
        raise

    return report


def _check_token_mismatch(user_id: str, billing_tokens: int, llm_tokens: int) -> Optional[Dict[str, object]]:
    """Check if BillingUsage.tokens_used vs LLMUsageLog.total_tokens mismatch."""
    diff = abs(billing_tokens - llm_tokens)
    if diff <= RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE:
        return None
    if billing_tokens > 0 and (diff / billing_tokens) * 100 <= RECONCILIATION_TOKEN_TOLERANCE_PERCENT:
        return None
    return {
        "user_id": user_id,
        "type": "token_mismatch",
        "internal_value": llm_tokens,
        "expected_value": billing_tokens,
        "severity": "critical" if diff > 1000 else "warning",
        "details": f"Token mismatch: billing={billing_tokens} llm={llm_tokens} diff={diff}",
    }


def _check_per_model_tokens(
    db: Session, user_id: str, billing_model_tokens: Dict[str, int], period: str
) -> List[Dict[str, object]]:
    """Check per-model token totals."""
    from models import LLMUsageLog
    discs = []

    for model, expected_tokens in billing_model_tokens.items():
        llm_tokens = db.exec(
            select(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
            .where(LLMUsageLog.user_id == user_id)
            .where(LLMUsageLog.model == model)
            .where(LLMUsageLog.created_at >= _period_start(period))
            .where(LLMUsageLog.created_at < _period_end(period))
        ).one()

        diff = abs(expected_tokens - llm_tokens)
        if diff > RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE:
            discs.append({
                "user_id": user_id,
                "type": "per_model_token_mismatch",
                "internal_value": llm_tokens,
                "expected_value": expected_tokens,
                "severity": "warning",
                "details": f"Model {model}: billing={expected_tokens} llm={llm_tokens}",
            })

    return discs


def _check_debate_count(user_id: str, billing_debates: int, actual_debates: int) -> Optional[Dict[str, object]]:
    """Check if BillingUsage.debates_created vs actual debate count mismatch."""
    diff = abs(billing_debates - actual_debates)
    if diff == 0:
        return None
    if billing_debates > 0 and (diff / billing_debates) * 100 <= RECONCILIATION_DEBATE_TOLERANCE_PERCENT:
        return None
    return {
        "user_id": user_id,
        "type": "debate_count_mismatch",
        "internal_value": actual_debates,
        "expected_value": billing_debates,
        "severity": "critical" if diff > 5 else "warning",
        "details": f"Debate mismatch: billing={billing_debates} actual={actual_debates}",
    }


def _check_orphan_usage(db: Session, period: str) -> List[Dict[str, object]]:
    """Check for LLM usage without a BillingUsage record."""
    from models import LLMUsageLog
    from billing.models import BillingUsage

    orphans = db.exec(
        select(LLMUsageLog.user_id, func.count().label("usage_count"))
        .where(LLMUsageLog.created_at >= _period_start(period))
        .where(LLMUsageLog.created_at < _period_end(period))
        .where(LLMUsageLog.user_id.not_in(
            select(BillingUsage.user_id).where(BillingUsage.period == period)
        ))
        .group_by(LLMUsageLog.user_id)
    ).all()

    return [
        {
            "user_id": row[0],
            "type": "orphan_usage",
            "internal_value": row[1],
            "expected_value": 0,
            "severity": "warning",
            "details": f"{row[1]} LLM calls with no BillingUsage record",
        }
        for row in orphans
    ]


def _check_cost_reconciliation(db: Session, period: str) -> List[Dict[str, object]]:
    """Check total cost_usd vs internal cost."""
    from models import LLMUsageLog

    total_cost = db.exec(
        select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0))
        .where(LLMUsageLog.created_at >= _period_start(period))
        .where(LLMUsageLog.created_at < _period_end(period))
    ).one()

    if total_cost > RECONCILIATION_COST_TOLERANCE_USD:
        return [{
            "user_id": "_system_",
            "type": "total_cost_exceeds_threshold",
            "internal_value": int(total_cost * 100),
            "expected_value": 0,
            "severity": "warning",
            "details": f"Total cost ${total_cost:.2f} exceeds threshold",
        }]
    return []


def _period_start(period: str) -> datetime:
    """Parse period string (YYYY-MM) and return start datetime."""
    try:
        return datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _period_end(period: str) -> datetime:
    """Parse period string (YYYY-MM) and return end datetime."""
    start = _period_start(period)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def get_last_reconciliation_time() -> Optional[datetime]:
    """Get the last reconciliation timestamp from Redis or in-memory cache."""
    try:
        from ratelimit import get_rate_limiter_backend
        backend = get_rate_limiter_backend()
        if hasattr(backend, "_client"):
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
    if (now - last_run).total_seconds() < 43200:
        return False
    return True


def record_reconciliation_time() -> None:
    """Record the reconciliation timestamp."""
    try:
        from ratelimit import get_rate_limiter_backend
        backend = get_rate_limiter_backend()
        if hasattr(backend, "_client"):
            backend._client.set(
                "reconciliation:last_run",
                datetime.now(timezone.utc).isoformat(),
                ex=86400 * 7,
            )
    except Exception:
        pass


def get_reconciliation_runs(
    db: Session, limit: int = 10, period: Optional[str] = None
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
    db: Session, run_id: uuid.UUID
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
