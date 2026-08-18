from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from fastapi import HTTPException, status
from integrations.events import emit_event
from sqlmodel import Session, select

from billing.models import BillingPlan, BillingSubscription, BillingUsage
from config import settings

UserID = Union[str, uuid.UUID]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_user_id(user_id: UserID) -> str:
    return str(user_id)


def _current_period() -> str:
    return _now().strftime("%Y-%m")


def get_active_plan(db: Session, user_id: UserID) -> BillingPlan:
    """Resolve the canonical plan entitlement for a user.

    Owner override wins first. Otherwise a subscription is entitled only while
    its billing period contains `now`. Stripe `trialing` is an entitled state,
    matching webhook behavior; future-dated or expired rows are never active.
    """
    uid = _normalize_user_id(user_id)

    from models import User
    from security.owner import is_owner

    user = db.get(User, uid)
    if is_owner(user):
        owner_slug = settings.OWNER_PLAN
        plan_ref = db.exec(select(BillingPlan).where(BillingPlan.slug == owner_slug)).first()
        if plan_ref:
            return plan_ref

    now = _now()
    stmt = (
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == uid,
            BillingSubscription.status.in_(["active", "trialing"]),
            BillingSubscription.current_period_start <= now,
            BillingSubscription.current_period_end > now,
        )
        .order_by(BillingSubscription.current_period_end.desc())
    )
    subscription = db.exec(stmt).first()
    if subscription:
        plan_ref = db.get(BillingPlan, subscription.plan_id)
        if plan_ref:
            return plan_ref

    plan_stmt = select(BillingPlan).where(BillingPlan.is_default_free.is_(True))
    plan = db.exec(plan_stmt).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="default billing plan missing")
    return plan


def get_or_create_usage(db: Session, user_id: UserID, period: Optional[str] = None) -> BillingUsage:
    uid = _normalize_user_id(user_id)
    period_value = period or _current_period()
    stmt = select(BillingUsage).where(BillingUsage.user_id == uid, BillingUsage.period == period_value)
    usage = db.exec(stmt).first()
    if not usage:
        usage = BillingUsage(user_id=uid, period=period_value)
        db.add(usage)
        db.flush()
    return usage


def check_limits_and_raise(db: Session, user_id: UserID, usage: BillingUsage) -> None:
    if settings.ENV == "test":
        return

    # Owner override
    from models import User
    from security.owner import is_owner

    user = db.get(User, _normalize_user_id(user_id))
    if is_owner(user) and settings.OWNER_UNLIMITED:
        import logging
        logging.getLogger(__name__).info(
            "owner_override_applied",
            extra={"user_id": str(user_id), "email": getattr(user, "email", None), "override_type": "billing_quota_bypass"}
        )
        return

    plan = get_active_plan(db, user_id)
    limits: Dict[str, object] = plan.limits or {}

    def _as_int(value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, (str, float)):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    max_debates = _as_int(limits.get("max_debates_per_month"))
    if max_debates is not None and usage.debates_created > max_debates:
        log_event("billing.limit_exceeded", user_id=str(user_id), metric="debates", limit=max_debates, current=usage.debates_created)
        emit_event(
            "usage_limit_exceeded",
            {"user_id": _normalize_user_id(user_id), "metric": "debates", "limit": max_debates},
        )
        from exceptions import RateLimitError
        raise RateLimitError(
            message="Billing limit for debates exceeded.",
            code="BILLING_LIMIT_DEBATES",
            details={"max": max_debates},
        )

    exports_flag = limits.get("exports_enabled", True)
    exports_allowed = exports_flag not in {False, "false", "False", "0"}
    if not exports_allowed and usage.exports_count > 0:
        log_event("billing.limit_exceeded", user_id=str(user_id), metric="exports", reason="disabled")
        emit_event(
            "usage_limit_exceeded",
            {"user_id": _normalize_user_id(user_id), "metric": "exports"},
        )
        from exceptions import RateLimitError
        raise RateLimitError(
            message="Exports are disabled for this account.",
            code="BILLING_LIMIT_EXPORTS_DISABLED",
        )


def _maybe_emit_nearing(user_id: UserID, metric: str, used: int, limit: Optional[int]) -> None:
    if not limit or limit <= 0:
        return
    threshold = max(1, int(limit * 0.8))
    if used == threshold:
        emit_event(
            "usage_limit_nearing",
            {"user_id": _normalize_user_id(user_id), "metric": metric, "current": used, "limit": limit},
        )


from log_config import log_event


def increment_debate_usage(db: Session, user_id: UserID) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.debates_created += 1
    usage.last_updated_at = _now()
    log_event("billing.usage.increment", user_id=str(user_id), metric="debates", value=1, total=usage.debates_created)
    check_limits_and_raise(db, user_id, usage)
    plan = get_active_plan(db, user_id)
    max_debates = plan.limits.get("max_debates_per_month")
    try:
        limit_int = int(max_debates) if max_debates is not None else None
    except (TypeError, ValueError):
        limit_int = None
    _maybe_emit_nearing(user_id, "debates", usage.debates_created, limit_int)
    return usage


def increment_export_usage(db: Session, user_id: UserID) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.exports_count += 1
    usage.last_updated_at = _now()
    log_event("billing.usage.increment", user_id=str(user_id), metric="exports", value=1, total=usage.exports_count)
    check_limits_and_raise(db, user_id, usage)
    return usage


def check_export_quota(db: Session, user_id: UserID) -> None:
    """
    Check if user can export (daily quota check) BEFORE generating export.
    Raises RateLimitError if quota exceeded.

    Patchset 65.B1
    """
    from exceptions import RateLimitError

    if settings.ENV == "test":
        return

    # Owner override
    from models import User
    from security.owner import is_owner
    user = db.get(User, _normalize_user_id(user_id))
    if is_owner(user) and settings.OWNER_UNLIMITED:
        import logging
        logging.getLogger(__name__).info(
            "owner_override_applied",
            extra={"user_id": str(user_id), "email": getattr(user, "email", None), "override_type": "export_quota_bypass"}
        )
        return

    plan = get_active_plan(db, user_id)
    limits: Dict[str, object] = plan.limits or {}

    # Check if exports are enabled
    exports_flag = limits.get("exports_enabled", True)
    exports_allowed = exports_flag not in {False, "false", "False", "0"}
    if not exports_allowed:
        log_event("billing.export_blocked", user_id=str(user_id), reason="disabled")
        raise RateLimitError(
            message="Exports are not available on your current plan.",
            code="quota.exports_disabled",
            details={"reason": "disabled", "plan": plan.slug},
        )

    # Check daily export limit
    max_exports_per_day = limits.get("max_exports_per_day")
    if max_exports_per_day is not None:
        if isinstance(max_exports_per_day, (str, int, float)):
            try:
                limit = int(max_exports_per_day)
            except ValueError:
                limit = None
        else:
            limit = None

        if limit is not None:
            usage = get_or_create_usage(db, user_id)
            if usage.exports_count >= limit:
                log_event("billing.export_blocked", user_id=str(user_id), reason="quota", limit=limit, used=usage.exports_count)
                raise RateLimitError(
                    message="Export quota exceeded. Please try again tomorrow or upgrade your plan.",
                    code="quota.exports_exceeded",
                    details={"limit": limit, "used": usage.exports_count, "window": "daily"},
                )


def add_tokens_usage(db: Session, user_id: UserID, model_id: str, tokens: int) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.tokens_used += int(tokens)
    model_totals = dict(usage.model_tokens or {})
    model_totals[model_id] = int(model_totals.get(model_id, 0)) + int(tokens)
    usage.model_tokens = model_totals
    usage.last_updated_at = _now()
    log_event("billing.usage.increment", user_id=str(user_id), metric="tokens", value=tokens, model_id=model_id, total=usage.tokens_used)
    return usage


def reserve_hosted_credit(
    db: Session,
    user_id: UserID,
    *,
    debate_id: str | None = None,
    run_attempt: int | None = None,
    continuation_id: str | None = None,
) -> str | None:
    """
    Reserve one hosted credit for a free-plan user.

    Atomic conditional UPDATE on the counter, plus a durable
    ``usage_ledger_entry`` row keyed by debate/attempt/continuation so
    refunds are exactly-once.

    Returns the ledger reservation id (or None if the user is not on free plan).
    Raises ValidationError if credits are exhausted.
    """
    import uuid as _uuid

    from exceptions import ValidationError
    from models import UsageLedgerEntry, User
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError
    from sqlmodel import select

    uid = _normalize_user_id(user_id)
    user = db.get(User, uid)
    if not user:
        return None

    plan = get_active_plan(db, uid)
    if not plan.is_default_free:
        return None

    # Durable ledger only when debate_id is known (exactly-once refund path).
    # Without debate_id: atomic counter only (legacy / race tests).
    attempt_part = run_attempt if run_attempt is not None else 0
    cont_part = continuation_id or "none"
    existing = None
    idempotency_key = None
    if debate_id:
        idempotency_key = f"credit_reserve:{debate_id}:a{attempt_part}:c{cont_part}"
        existing = db.exec(
            select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == idempotency_key)
        ).first()
        if existing:
            if (
                existing.user_id == uid
                and existing.kind == "credit_reservation"
                and existing.debate_id == debate_id
            ):
                return existing.id
            raise ValidationError(
                message="Hosted-credit reservation identity conflicts with its billing context.",
                code="hosted_credits.reservation_conflict",
            )

    limit = getattr(user, "hosted_credits_limit", 10)

    def _increment_counter() -> None:
        stmt = (
            update(User)
            .where(User.id == uid)
            .where(User.hosted_credits_used < User.hosted_credits_limit)
            .values(hosted_credits_used=User.hosted_credits_used + 1)
            .execution_options(synchronize_session=False)
        )
        result = db.exec(stmt)
        if result.rowcount == 0:
            db.refresh(user)
            used = getattr(user, "hosted_credits_used", 0)
            raise ValidationError(
                message=f"You have exhausted your free hosted runs ({used}/{limit}).",
                code="hosted_credits.exhausted",
                hint="Please upgrade to a Pro plan, add your own API key under Settings, or run a mock/demo run.",
            )
        db.expire(user, ["hosted_credits_used"])

    if not debate_id or not idempotency_key:
        _increment_counter()
        return None

    entry = UsageLedgerEntry(
        id=str(_uuid.uuid4()),
        user_id=uid,
        kind="credit_reservation",
        status="reserved",
        idempotency_key=idempotency_key,
        amount=1,
        debate_id=debate_id,
        meta={"run_attempt": attempt_part, "continuation_id": continuation_id},
    )
    try:
        # The savepoint keeps a losing idempotency insert from rolling back the
        # caller's surrounding debate/continuation transaction.
        with db.begin_nested():
            db.add(entry)
            db.flush()
            _increment_counter()
    except IntegrityError:
        existing = db.exec(
            select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == idempotency_key)
        ).first()
        if (
            existing
            and existing.user_id == uid
            and existing.kind == "credit_reservation"
            and existing.debate_id == debate_id
        ):
            return existing.id
        raise
    return entry.id


def _reservation_matches(
    entry: object,
    *,
    user_id: str,
    debate_id: str | None,
) -> bool:
    """Reject reservation identifiers that do not belong to this billing context."""
    return bool(
        entry
        and getattr(entry, "user_id", None) == user_id
        and getattr(entry, "kind", None) == "credit_reservation"
        and (debate_id is None or getattr(entry, "debate_id", None) == debate_id)
    )


def refund_hosted_credit(
    db: Session,
    user_id: UserID,
    *,
    reservation_id: str | None = None,
    debate_id: str | None = None,
) -> bool:
    """
    Exactly-once refund for a free-plan hosted credit reservation.

    Prefers ``reservation_id`` (ledger row). Falls back to latest reserved
    credit_reservation for ``debate_id``. Counter decrement only runs when the
    ledger row transitions reserved → refunded in the same transaction.

    Returns True if a credit was refunded, False if already settled/refunded
    or no reservation found.
    """
    from datetime import datetime, timezone

    from models import UsageLedgerEntry, User
    from sqlalchemy import update
    from sqlmodel import select

    uid = _normalize_user_id(user_id)
    user = db.get(User, uid)
    if not user:
        return False

    entry: UsageLedgerEntry | None = None
    if reservation_id:
        if not debate_id:
            return False
        entry = db.get(UsageLedgerEntry, reservation_id)
    elif debate_id:
        entry = db.exec(
            select(UsageLedgerEntry)
            .where(UsageLedgerEntry.debate_id == debate_id)
            .where(UsageLedgerEntry.kind == "credit_reservation")
            .where(UsageLedgerEntry.status.in_(["reserved", "settlement_pending"]))
            .where(UsageLedgerEntry.user_id == uid)
            .order_by(UsageLedgerEntry.created_at.desc())
        ).first()

    if entry is not None and not _reservation_matches(
        entry, user_id=uid, debate_id=debate_id
    ):
        return False

    if entry is None:
        # Legacy path without ledger row: single atomic counter floor (not exactly-once)
        if reservation_id is None and debate_id is None:
            stmt = (
                update(User)
                .where(User.id == uid)
                .where(User.hosted_credits_used > 0)
                .values(hosted_credits_used=User.hosted_credits_used - 1)
                .execution_options(synchronize_session=False)
            )
            result = db.exec(stmt)
            db.expire(user, ["hosted_credits_used"])
            return bool(result.rowcount)
        return False

    if entry.status not in {"reserved", "settlement_pending"}:
        return False

    # Conditional transition — only one concurrent caller wins
    now = datetime.now(timezone.utc)
    transition = (
        update(UsageLedgerEntry)
        .where(UsageLedgerEntry.id == entry.id)
        .where(UsageLedgerEntry.status.in_(["reserved", "settlement_pending"]))
        .values(status="refunded", refunded_at=now)
        .execution_options(synchronize_session=False)
    )
    tr = db.exec(transition)
    if tr.rowcount == 0:
        return False

    stmt = (
        update(User)
        .where(User.id == uid)
        .where(User.hosted_credits_used > 0)
        .values(hosted_credits_used=User.hosted_credits_used - 1)
        .execution_options(synchronize_session=False)
    )
    db.exec(stmt)
    db.expire(user, ["hosted_credits_used"])
    return True


def consume_hosted_credit(
    db: Session,
    user_id: UserID,
    *,
    reservation_id: str | None = None,
    debate_id: str | None = None,
) -> bool:
    """
    Mark a hosted credit reservation as consumed (successful completion).

    Does not decrement the counter — reservation already consumed the credit.
    """
    from datetime import datetime, timezone

    from models import UsageLedgerEntry
    from sqlalchemy import update
    from sqlmodel import select

    entry: UsageLedgerEntry | None = None
    uid = _normalize_user_id(user_id)
    if reservation_id:
        if not debate_id:
            return False
        entry = db.get(UsageLedgerEntry, reservation_id)
    elif debate_id:
        entry = db.exec(
            select(UsageLedgerEntry)
            .where(UsageLedgerEntry.debate_id == debate_id)
            .where(UsageLedgerEntry.kind == "credit_reservation")
            .where(UsageLedgerEntry.status.in_(["reserved", "settlement_pending"]))
            .where(UsageLedgerEntry.user_id == uid)
            .order_by(UsageLedgerEntry.created_at.desc())
        ).first()

    if (
        entry is None
        or not _reservation_matches(entry, user_id=uid, debate_id=debate_id)
        or entry.status not in {"reserved", "settlement_pending"}
    ):
        return False

    now = datetime.now(timezone.utc)
    transition = (
        update(UsageLedgerEntry)
        .where(UsageLedgerEntry.id == entry.id)
        .where(UsageLedgerEntry.status.in_(["reserved", "settlement_pending"]))
        .values(status="settled", settled_at=now)
        .execution_options(synchronize_session=False)
    )
    result = db.exec(transition)
    return bool(result.rowcount)
