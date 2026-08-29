"""Crash-safe terminal accounting reconciliation.

Gateway calls reserve daily tokens before provider work and settle that
reservation to actual usage on return. Terminal attempt reconciliation applies
only any remaining aggregate delta (legacy/non-gateway work), while also
repairing hosted-credit settlement after crashes.

Traffic-readiness invariant: periodic reconciliation must scale with unresolved
work, not with the entire historical DebateAttempt table. Candidate discovery
therefore anti-joins only *fully accounted* aggregate token ledger rows and
processes a bounded batch on every cleanup tick.
"""

from __future__ import annotations

import asyncio
import logging

import sqlalchemy as sa
from database import session_scope
from models import Debate, DebateAttempt, DebateContinuation, UsageLedgerEntry
from sqlmodel import select

logger = logging.getLogger(__name__)

_installed = False
_original_cleanup = None

_TOKEN_PENDING = {"reserved", "settlement_pending", "reconciliation_pending"}
_CREDIT_PENDING = {"reserved", "settlement_pending"}
_SUCCESS_DEBATE_STATUSES = {"completed", "completed_with_warnings"}
_FAILED_DEBATE_STATUSES = {"failed", "cancelled"}
_TERMINAL_ATTEMPT_STATUSES = {"completed", "failed", "cancelled"}
_RECONCILE_BATCH_SIZE = 500


def _gateway_accounted_tokens(session, attempt_id: str | None) -> int:
    """Return quota already charged by gateway reservations for this attempt.

    ``reserved`` entries count too: the daily counter was incremented when the
    reservation was created. Ignoring an unresolved reservation after a worker
    crash would make terminal reconciliation add the same tokens again.
    """
    if not attempt_id:
        return 0
    entries = session.exec(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.kind == "gateway_token_usage",
            UsageLedgerEntry.status.in_(["reserved", "settled"]),
            UsageLedgerEntry.attempt_id == attempt_id,
        )
    ).all()
    return sum(max(int(entry.amount or 0), 0) for entry in entries)


def ensure_token_accounting_once(
    session,
    *,
    debate: Debate,
    attempt: DebateAttempt,
) -> bool:
    """Settle aggregate attempt usage and apply only the uncounted daily delta."""
    if not debate.user_id:
        return False
    tokens = max(int(attempt.tokens_used or 0), 0)
    if tokens <= 0:
        return False

    from services.usage_ledger import record_token_usage, settle_token_usage

    entry = record_token_usage(
        session,
        user_id=debate.user_id,
        debate_id=debate.id,
        attempt_id=attempt.id,
        tokens=tokens,
    )
    if entry.status in _TOKEN_PENDING:
        settle_token_usage(
            session,
            user_id=debate.user_id,
            debate_id=debate.id,
            attempt_id=attempt.id,
        )
        session.refresh(entry)

    if entry.status != "settled":
        return False

    meta = dict(entry.meta or {})
    if meta.get("daily_counter_applied") is True:
        return False

    gateway_tokens = _gateway_accounted_tokens(session, attempt.id)
    delta = max(tokens - gateway_tokens, 0)
    if delta > 0:
        from usage_limits import record_token_usage as apply_daily_token_usage

        apply_daily_token_usage(
            session,
            debate.user_id,
            delta,
            commit=False,
        )

    meta.update(
        {
            "daily_counter_applied": True,
            "attempt_tokens": tokens,
            "gateway_accounted_tokens": gateway_tokens,
            "aggregate_delta_applied": delta,
        }
    )
    entry.meta = meta
    session.add(entry)
    session.flush()
    return delta > 0


def _settle_credit_entry(session, entry: UsageLedgerEntry) -> str | None:
    """Reconcile one pending hosted-credit reservation from durable state."""
    if entry.status not in _CREDIT_PENDING:
        return None

    from billing.service import consume_hosted_credit, refund_hosted_credit

    debate = session.get(Debate, entry.debate_id) if entry.debate_id else None
    if debate is None or not debate.user_id:
        return None
    if entry.user_id != debate.user_id:
        logger.error(
            "billing.reconcile_identity_mismatch entry=%s debate=%s entry_user=%s debate_user=%s",
            entry.id,
            debate.id,
            entry.user_id,
            debate.user_id,
        )
        return None

    meta = dict(entry.meta or {})
    continuation_id = meta.get("continuation_id")
    if continuation_id:
        continuation = session.get(DebateContinuation, str(continuation_id))
        if continuation is None or continuation.debate_id != debate.id:
            return None
        if continuation.status == "completed":
            changed = consume_hosted_credit(
                session,
                debate.user_id,
                reservation_id=entry.id,
                debate_id=debate.id,
            )
            return "settled" if changed else None
        if continuation.status in {"failed", "cancelled"}:
            changed = refund_hosted_credit(
                session,
                debate.user_id,
                reservation_id=entry.id,
                debate_id=debate.id,
            )
            return "refunded" if changed else None
        return None

    entry_attempt = int(meta.get("run_attempt", 0) or 0)
    debate_attempt = max(int(debate.run_attempt or 0), 1)
    if entry_attempt > 0 and entry_attempt < debate_attempt and debate.status in (
        _SUCCESS_DEBATE_STATUSES | _FAILED_DEBATE_STATUSES
    ):
        changed = refund_hosted_credit(
            session,
            debate.user_id,
            reservation_id=entry.id,
            debate_id=debate.id,
        )
        return "refunded" if changed else None

    if debate.status in _SUCCESS_DEBATE_STATUSES:
        changed = consume_hosted_credit(
            session,
            debate.user_id,
            reservation_id=entry.id,
            debate_id=debate.id,
        )
        return "settled" if changed else None
    if debate.status in _FAILED_DEBATE_STATUSES:
        changed = refund_hosted_credit(
            session,
            debate.user_id,
            reservation_id=entry.id,
            debate_id=debate.id,
        )
        return "refunded" if changed else None
    return None


def _unresolved_terminal_attempts(session) -> list[DebateAttempt]:
    """Return only terminal attempts without a fully-applied aggregate ledger.

    Historical deployments may already contain ``token_usage`` rows whose
    status is ``settled`` but which predate the atomic ``daily_counter_applied``
    marker. Those rows are still reconciliation candidates. SQLAlchemy's JSON
    comparator compiles the boolean path appropriately for both PostgreSQL and
    SQLite, preserving migration/test parity.
    """
    fully_accounted = sa.and_(
        UsageLedgerEntry.attempt_id == DebateAttempt.id,
        UsageLedgerEntry.kind == "token_usage",
        UsageLedgerEntry.status == "settled",
        UsageLedgerEntry.meta["daily_counter_applied"].as_boolean().is_(True),
    )
    stmt = (
        select(DebateAttempt)
        .join(Debate, Debate.id == DebateAttempt.debate_id)
        .outerjoin(UsageLedgerEntry, fully_accounted)
        .where(DebateAttempt.status.in_(_TERMINAL_ATTEMPT_STATUSES))
        .where(DebateAttempt.tokens_used > 0)
        .where(Debate.user_id.is_not(None))
        .where(UsageLedgerEntry.id.is_(None))
        .limit(_RECONCILE_BATCH_SIZE)
    )
    return list(session.exec(stmt).all())


def reconcile_terminal_accounting_sync() -> dict[str, int]:
    """Repair reconstructible accounting drift in bounded unresolved batches."""
    stats = {
        "token_candidates": 0,
        "token_counters_applied": 0,
        "credit_candidates": 0,
        "credits_settled": 0,
        "credits_refunded": 0,
    }

    with session_scope() as session:
        attempts = _unresolved_terminal_attempts(session)
        stats["token_candidates"] = len(attempts)
        for attempt in attempts:
            debate = session.get(Debate, attempt.debate_id)
            if debate is None:
                continue
            if ensure_token_accounting_once(
                session,
                debate=debate,
                attempt=attempt,
            ):
                stats["token_counters_applied"] += 1

        credit_entries = list(
            session.exec(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.kind == "credit_reservation")
                .where(UsageLedgerEntry.status.in_(_CREDIT_PENDING))
                .limit(_RECONCILE_BATCH_SIZE)
            ).all()
        )
        stats["credit_candidates"] = len(credit_entries)
        for entry in credit_entries:
            outcome = _settle_credit_entry(session, entry)
            if outcome == "settled":
                stats["credits_settled"] += 1
            elif outcome == "refunded":
                stats["credits_refunded"] += 1

    if stats["token_counters_applied"] or stats["credits_settled"] or stats["credits_refunded"]:
        logger.warning("terminal_accounting.reconciled stats=%s", stats)
    return stats


async def reconcile_terminal_accounting() -> dict[str, int]:
    return await asyncio.get_running_loop().run_in_executor(
        None,
        reconcile_terminal_accounting_sync,
    )


async def _cleanup_with_terminal_reconciliation():
    try:
        await reconcile_terminal_accounting()
    except Exception:
        logger.exception("terminal_accounting.reconciliation_failed")
    return await _original_cleanup()


def install_terminal_accounting_reconciler() -> None:
    """Attach reconciliation to the periodic cleanup loop exactly once."""
    global _installed, _original_cleanup
    if _installed:
        return

    import orchestrator_cleanup

    _original_cleanup = orchestrator_cleanup.cleanup_stale_debates
    orchestrator_cleanup.cleanup_stale_debates = _cleanup_with_terminal_reconciliation
    _installed = True
