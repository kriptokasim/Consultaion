"""Cost reconciliation job.

Cross-references BillingUsage against LLMUsageLog to detect real discrepancies
in token counts, per-model usage, debate counts, hosted credits, and orphans.
Runs as a background task. Supports daily detection runs and monthly full reconciliation.

Uses ReconciliationWindow for explicit time-window boundaries.
Cost reconciliation compares recorded cost_usd with independently recomputed
cost using versioned model pricing.
"""

from __future__ import annotations

import dataclasses
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from config import settings
from sqlmodel import Session, select, func, col

logger = logging.getLogger(__name__)

RECONCILIATION_VERSION = "v2"
RECONCILIATION_INTERVAL_SECONDS = 86400
RECONCILIATION_HOUR = 3

# Tolerance thresholds
RECONCILIATION_TOKEN_TOLERANCE_ABSOLUTE = 100
RECONCILIATION_TOKEN_TOLERANCE_PERCENT = 5.0
RECONCILIATION_COST_TOLERANCE_USD = 1.0
RECONCILIATION_COST_TOLERANCE_PERCENT = 10.0
RECONCILIATION_DEBATE_TOLERANCE_PERCENT = 2.0


@dataclasses.dataclass
class ReconciliationWindow:
    """Explicit time-window boundaries for reconciliation."""
    start_at: datetime
    end_at: datetime
    label: str

    @classmethod
    def previous_utc_day(cls) -> ReconciliationWindow:
        """Window covering the previous UTC day."""
        now = datetime.now(timezone.utc)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        label = start.strftime("%Y-%m-%d")
        return cls(start_at=start, end_at=end, label=label)

    @classmethod
    def month_to_date(cls) -> ReconciliationWindow:
        """Window from start of current month to now."""
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = f"{start.strftime('%Y-%m')}-to-date"
        return cls(start_at=start, end_at=now, label=label)

    @classmethod
    def closed_month(cls, year: int, month: int) -> ReconciliationWindow:
        """Window for a fully closed calendar month."""
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        label = start.strftime("%Y-%m")
        return cls(start_at=start, end_at=end, label=label)

    @classmethod
    def from_period(cls, period: str) -> ReconciliationWindow:
        """Parse YYYY-MM period string into a month window."""
        try:
            start = datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            return cls(start_at=start, end_at=end, label=period)
        except ValueError:
            now = datetime.now(timezone.utc)
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
            return cls(start_at=start, end_at=end, label="unknown")

    def period_str(self) -> str:
        """Return the month label (YYYY-MM) for backward compatibility."""
        return self.start_at.strftime("%Y-%m")

    def run_key(self, run_type: str) -> str:
        """Generate deterministic run key for idempotency."""
        return f"{run_type}:{self.start_at.isoformat()}:{self.end_at.isoformat()}:{RECONCILIATION_VERSION}"


def _get_model_pricing() -> Dict[str, Dict[str, float]]:
    """Return a versioned snapshot of model pricing.

    Format: {model_id: {"input_price_per_1k": float, "output_price_per_1k": float}}
    This acts as a static snapshot for reconciliation consistency.
    """
    # Static pricing snapshot keyed by model ID
    # Values are USD per 1000 tokens
    return {
        "openai/gpt-4o": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.03},
        "openai/gpt-4o-mini": {"input_price_per_1k": 0.0015, "output_price_per_1k": 0.006},
        "openai/gpt-4-turbo": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.03},
        "anthropic/claude-3-5-sonnet-20240620": {"input_price_per_1k": 0.003, "output_price_per_1k": 0.015},
        "anthropic/claude-3-haiku": {"input_price_per_1k": 0.00025, "output_price_per_1k": 0.00125},
        "anthropic/claude-3-opus": {"input_price_per_1k": 0.015, "output_price_per_1k": 0.075},
        "gemini/gemini-1.5-pro": {"input_price_per_1k": 0.0035, "output_price_per_1k": 0.0105},
        "gemini/gemini-1.5-flash": {"input_price_per_1k": 0.00035, "output_price_per_1k": 0.00105},
        "deepseek/deepseek-chat": {"input_price_per_1k": 0.00027, "output_price_per_1k": 0.0011},
        "deepseek/deepseek-reasoner": {"input_price_per_1k": 0.00055, "output_price_per_1k": 0.00219},
    }


def _recompute_cost(prompt_tokens: int, completion_tokens: int, model: str, pricing: Dict[str, Dict[str, float]]) -> Optional[float]:
    """Recompute expected cost from token counts using model pricing snapshot."""
    model_pricing = pricing.get(model)
    if not model_pricing:
        return None
    input_cost = (prompt_tokens / 1000) * model_pricing["input_price_per_1k"]
    output_cost = (completion_tokens / 1000) * model_pricing["output_price_per_1k"]
    return round(input_cost + output_cost, 6)


def reconcile_usage(
    db: Session,
    window: Optional[ReconciliationWindow] = None,
    run_type: str = "daily",
) -> Dict[str, object]:
    """Cross-reference BillingUsage against LLMUsageLog for real discrepancies.

    Uses ReconciliationWindow for explicit time boundaries.
    Cost reconciliation compares recorded SUM(cost_usd) vs independently
    recomputed cost from token counts and model pricing.
    """
    from billing.models import (
        BillingUsage,
        BillingReconciliationRun,
        BillingReconciliationDiscrepancy,
    )
    from billing.service import _current_period
    from models import LLMUsageLog, Debate

    if window is None:
        window = ReconciliationWindow.previous_utc_day()

    target_period = window.period_str()
    run_id = uuid.uuid4()
    run_key = window.run_key(run_type)

    # Check for existing run with same key to prevent duplicates
    existing = db.exec(
        select(BillingReconciliationRun).where(
            BillingReconciliationRun.period == target_period,
            BillingReconciliationRun.run_type == run_type,
            BillingReconciliationRun.status == "completed",
        )
    ).first()
    if existing:
        logger.info(
            "Skipping duplicate reconciliation: period=%s run_type=%s existing_run=%s",
            target_period, run_type, existing.id,
        )
        return {
            "run_id": str(existing.id),
            "version": RECONCILIATION_VERSION,
            "period": target_period,
            "run_type": run_type,
            "skipped": True,
            "users_checked": existing.users_checked,
            "discrepancies": [],
            "total_tokens_internal": existing.total_tokens_internal,
            "total_tokens_usage": existing.total_tokens_usage,
        }

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
        "window_start": window.start_at.isoformat(),
        "window_end": window.end_at.isoformat(),
        "run_key": run_key,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "users_checked": 0,
        "discrepancies": [],
        "total_tokens_internal": 0,
        "total_tokens_usage": 0,
        "skipped": False,
    }

    try:
        usages = db.exec(
            select(BillingUsage).where(BillingUsage.period == target_period)
        ).all()

        pricing = _get_model_pricing()
        discrepancies: List[Dict[str, object]] = []

        for usage in usages:
            report["users_checked"] += 1
            report["total_tokens_usage"] += usage.tokens_used

            # 1. Token reconciliation: BillingUsage.tokens_used vs SUM(LLMUsageLog.total_tokens)
            llm_tokens = db.exec(
                select(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                .where(LLMUsageLog.user_id == usage.user_id)
                .where(LLMUsageLog.created_at >= window.start_at)
                .where(LLMUsageLog.created_at < window.end_at)
            ).one()
            report["total_tokens_internal"] += llm_tokens

            disc = _check_token_mismatch(usage.user_id, usage.tokens_used, llm_tokens)
            if disc:
                discrepancies.append(disc)

            # 2. Per-model reconciliation: BillingUsage.model_tokens vs grouped LLMUsageLog
            if usage.model_tokens:
                per_model_discs = _check_per_model_tokens(
                    db, usage.user_id, usage.model_tokens, window
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
        orphan_discs = _check_orphan_usage(db, window)
        discrepancies.extend(orphan_discs)

        # 7. Cost reconciliation: compare recorded SUM(cost_usd) vs independently recomputed
        cost_discs = _check_cost_reconciliation(db, window)
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
            "Reconciliation complete: period=%s run_key=%s users=%d discrepancies=%d run_id=%s version=%s",
            target_period,
            run_key,
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
    db: Session, user_id: str, billing_model_tokens: Dict[str, int], window: ReconciliationWindow
) -> List[Dict[str, object]]:
    """Check per-model token totals."""
    from models import LLMUsageLog
    discs = []

    for model, expected_tokens in billing_model_tokens.items():
        llm_tokens = db.exec(
            select(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
            .where(LLMUsageLog.user_id == user_id)
            .where(LLMUsageLog.model == model)
            .where(LLMUsageLog.created_at >= window.start_at)
            .where(LLMUsageLog.created_at < window.end_at)
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


def _check_orphan_usage(db: Session, window: ReconciliationWindow) -> List[Dict[str, object]]:
    """Check for LLM usage without a BillingUsage record."""
    from models import LLMUsageLog
    from billing.models import BillingUsage

    period = window.period_str()
    orphans = db.exec(
        select(LLMUsageLog.user_id, func.count().label("usage_count"))
        .where(LLMUsageLog.created_at >= window.start_at)
        .where(LLMUsageLog.created_at < window.end_at)
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


def _check_cost_reconciliation(db: Session, window: ReconciliationWindow) -> List[Dict[str, object]]:
    """Compare recorded SUM(cost_usd) vs independently recomputed cost.

    Recomputed cost uses input_tokens × input_price + output_tokens × output_price
    from a versioned model-pricing snapshot.
    """
    from models import LLMUsageLog

    pricing = _get_model_pricing()
    records = db.exec(
        select(LLMUsageLog)
        .where(LLMUsageLog.created_at >= window.start_at)
        .where(LLMUsageLog.created_at < window.end_at)
    ).all()

    if not records:
        return []

    total_recorded: float = 0.0
    total_recomputed: float = 0.0
    per_model: Dict[str, dict] = {}
    unknown_models: set = set()

    for rec in records:
        total_recorded += rec.cost_usd or 0.0
        recomputed = _recompute_cost(
            rec.prompt_tokens, rec.completion_tokens, rec.model, pricing
        )
        if recomputed is not None:
            total_recomputed += recomputed
            if rec.model not in per_model:
                per_model[rec.model] = {"recorded": 0.0, "recomputed": 0.0}
            per_model[rec.model]["recorded"] += rec.cost_usd or 0.0
            per_model[rec.model]["recomputed"] += recomputed
        else:
            unknown_models.add(rec.model)

    discrepancies: List[Dict[str, object]] = []

    # Unknown model pricing
    for model in sorted(unknown_models):
        discrepancies.append({
            "user_id": "_system_",
            "type": "unknown_model_pricing",
            "internal_value": 0,
            "expected_value": 0,
            "severity": "warning",
            "details": f"Unknown model pricing for '{model}'; cannot recompute cost",
        })

    # Total cost discrepancy
    cost_diff = abs(total_recorded - total_recomputed)
    cost_diff_pct = (cost_diff / total_recomputed * 100) if total_recomputed > 0 else 0.0

    if cost_diff > RECONCILIATION_COST_TOLERANCE_USD and cost_diff_pct > RECONCILIATION_COST_TOLERANCE_PERCENT:
        discrepancies.append({
            "user_id": "_system_",
            "type": "cost_reconciliation_mismatch",
            "internal_value": int(total_recomputed * 100),
            "expected_value": int(total_recorded * 100),
            "severity": "critical" if cost_diff > 5.0 else "warning",
            "details": (
                f"Cost mismatch: recorded=${total_recorded:.4f} "
                f"recomputed=${total_recomputed:.4f} "
                f"diff=${cost_diff:.4f} ({cost_diff_pct:.1f}%)"
            ),
        })

    # Per-model cost discrepancies
    for model, costs in per_model.items():
        rec = costs["recorded"]
        recom = costs["recomputed"]
        d = abs(rec - recom)
        if d > 0.01 and (recom > 0 and (d / recom * 100) > 5.0):
            discrepancies.append({
                "user_id": "_system_",
                "type": "per_model_cost_mismatch",
                "internal_value": int(recom * 100),
                "expected_value": int(rec * 100),
                "severity": "warning",
                "details": (
                    f"Model {model}: recorded=${rec:.4f} "
                    f"recomputed=${recom:.4f} diff=${d:.4f}"
                ),
            })

    return discrepancies


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
