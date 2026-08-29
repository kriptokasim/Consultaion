"""Crash-safe terminal accounting reconciliation.

Terminal product state is committed before accounting side effects. That is the
correct ordering for user-visible durability, but it creates a crash window:
a worker can die after Debate/DebateAttempt become terminal and before hosted
credit settlement or daily token accounting is applied.

This module makes those side effects reconstructible and idempotent:

* token usage is keyed by debate+attempt in UsageLedgerEntry;
* the daily UsageCounter increment and a ``daily_counter_applied`` ledger flag
  are committed in the same transaction, preventing double-count on retries;
* reserved hosted-credit rows are settled/refunded from durable Debate or
  DebateContinuation terminal state;
* the periodic stale-cleanup loop runs this reconciliation even when there are
  no stale debates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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


def ensure_token_accounting_once(
    session,
    *,
    debate: Debate,
    attempt: DebateAttempt,
) -> bool:
    """Ensure ledger settlement + daily token quota exactly once for an attempt.

    Returns True when this call applied the daily counter, False when it was
    already accounted or there was nothing to account.
    """
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
        # settle_token_usage mutates the same identity-map row, but refresh to
        # make the persisted terminal state explicit before applying metadata.
        session.refresh(entry)

    if entry.status != "settled":
        return False

    meta = dict(entry.meta or {})
    if meta.get("daily_counter_applied") is True:
        return False

    # Crucially, this counter increment and the ledger flag share one DB
    # transaction. A crash rolls back both; a committed retry sees the flag and
    # cannot increment a second time.
    from usage_limits import record_token_usage as apply_daily_token_usage

    apply_daily_token_usage(
        session,
        debate.user_id,
        tokens,
        commit=False,
    )
    meta.update(
        {
            "daily_counter_applied": True,
            "accounted_tokens": tokens,
        }
    )
    entry.meta = meta
    session.add(entry)
    session.flush()
    return True


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

    # Full-attempt reservation. Older active reservations are superseded once a
    # later attempt itself is terminal; refund them rather than consuming two
    # credits for one logical debate history.
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


def reconcile_terminal_accounting_sync() -> dict[str, int]:
    """Repair reconstructible terminal accounting drift in one transaction."""
    stats = {
        "token_counters_applied": 0,
        "credits_settled": 0,
        "credits_refunded": 0,
    }

    with session_scope() as session:
        attempts = list(
            session.exec(
                select(DebateAttempt)
                .where(DebateAttempt.status.in_(_TERMINAL_ATTEMPT_STATUSES))
                .where(DebateAttempt.tokens_used > 0)
            ).all()
        )
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
            ).all()
        )
        for entry in credit_entries:
            outcome = _settle_credit_entry(session, entry)
            if outcome == "settled":
                stats["credits_settled"] += 1
            elif outcome == "refunded":
                stats["credits_refunded"] += 1

    if any(stats.values()):
        logger.warning("terminal_accounting.reconciled stats=%s", stats)
    return stats


async def reconcile_terminal_accounting() -> dict[str, int]:
    return await asyncio.get_running_loop().run_in_executor(
        None,
        reconcile_terminal_accounting_sync,
    )


async def _cleanup_with_terminal_reconciliation():
    # Accounting repair should not be coupled to whether stale-run discovery
    # succeeds. Run it first, log failures, and always continue cleanup.
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
