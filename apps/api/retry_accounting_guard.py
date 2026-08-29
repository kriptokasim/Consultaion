"""Hosted-credit accounting guard for full debate retries.

A full retry creates a new attempt reservation and points
``Debate.credit_reservation_id`` at it before dispatch. Legacy retry code then
refunded the previous attempt reservation *before* the Celery hand-off. If the
broker rejected the task, compensation restored the old reservation ID on the
Debate row even though that ledger entry was already terminal ``refunded``.

This guard defers exactly that superseded-attempt refund while the replacement
run is only ``scheduled``. Once dispatch succeeds, stale active attempt
reservations are reconciled. If dispatch fails, the existing compensation can
safely restore the still-reserved prior identity.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from models import Debate, UsageLedgerEntry
from sqlmodel import select

logger = logging.getLogger(__name__)

_installed = False
_original_refund = None
_original_dispatch = None


def _is_superseded_retry_refund(db, reservation_id: str | None, debate_id: str | None) -> bool:
    if not reservation_id or not debate_id:
        return False

    debate = db.get(Debate, debate_id)
    if (
        debate is None
        or debate.status != "scheduled"
        or not debate.credit_reservation_id
        or debate.credit_reservation_id == reservation_id
    ):
        return False

    entry = db.get(UsageLedgerEntry, reservation_id)
    if entry is None or entry.kind != "credit_reservation" or entry.status not in {
        "reserved",
        "settlement_pending",
    }:
        return False

    meta = entry.meta or {}
    # Continuations own their reservation independently and already have an
    # atomic compensation path. Only full-attempt retry reservations are
    # deferred here.
    return not meta.get("continuation_id")


def _guarded_refund_hosted_credit(
    db,
    user_id,
    *,
    reservation_id: str | None = None,
    debate_id: str | None = None,
):
    if _is_superseded_retry_refund(db, reservation_id, debate_id):
        logger.info(
            "billing.retry_refund_deferred debate_id=%s reservation_id=%s active_reservation_id=%s",
            debate_id,
            reservation_id,
            getattr(db.get(Debate, debate_id), "credit_reservation_id", None),
        )
        return False
    return _original_refund(
        db,
        user_id,
        reservation_id=reservation_id,
        debate_id=debate_id,
    )


def _refund_superseded_attempt_reservations(debate_id: str) -> int:
    """Refund non-current active attempt reservations after dispatch succeeds."""
    from database import session_scope

    changed = 0
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if debate is None or not debate.user_id:
            return 0

        active_id = debate.credit_reservation_id
        entries = list(
            session.exec(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.debate_id == debate_id)
                .where(UsageLedgerEntry.kind == "credit_reservation")
                .where(UsageLedgerEntry.status.in_(["reserved", "settlement_pending"]))
            ).all()
        )
        for entry in entries:
            if entry.id == active_id:
                continue
            meta = entry.meta or {}
            if meta.get("continuation_id"):
                continue
            if _original_refund(
                session,
                debate.user_id,
                reservation_id=entry.id,
                debate_id=debate_id,
            ):
                changed += 1

    if changed:
        logger.info(
            "billing.retry_superseded_reservations_refunded debate_id=%s count=%s",
            debate_id,
            changed,
        )
    return changed


async def _guarded_dispatch_debate_run(*args, **kwargs):
    """Reconcile prior retry reservations only after successful hand-off/run."""
    await _original_dispatch(*args, **kwargs)

    debate_id = str(args[0] if args else kwargs.get("debate_id") or "")
    resume = bool(kwargs.get("resume", False))
    continuation_id = kwargs.get("continuation_id")
    if debate_id and resume and not continuation_id:
        await asyncio.get_running_loop().run_in_executor(
            None,
            _refund_superseded_attempt_reservations,
            debate_id,
        )


def install_retry_accounting_guard() -> None:
    """Install retry accounting hooks once in API/worker runtime."""
    global _installed, _original_refund, _original_dispatch
    if _installed:
        return

    import billing.service as billing_service
    import debate_dispatch

    _original_refund = billing_service.refund_hosted_credit
    _original_dispatch = debate_dispatch.dispatch_debate_run

    billing_service.refund_hosted_credit = _guarded_refund_hosted_credit
    debate_dispatch.dispatch_debate_run = _guarded_dispatch_debate_run

    # Route modules import dispatch_debate_run by value. Patch already-loaded
    # bindings without importing routers into Celery-only processes.
    for module_name in (
        "routes.debates.hardening",
        "routes.debates.execution",
        "routes.debates.crud",
    ):
        module = sys.modules.get(module_name)
        if module is not None and getattr(module, "dispatch_debate_run", None) is _original_dispatch:
            module.dispatch_debate_run = _guarded_dispatch_debate_run

    _installed = True
