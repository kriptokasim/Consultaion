"""Usage Ledger Service — idempotent accounting for all billing operations.

FH125: Every billing operation writes to UsageLedgerEntry with an idempotency key.
This provides exactly-once semantics for token usage, credit lifecycle, and exports.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from models import UsageLedgerEntry

logger = logging.getLogger(__name__)


def _idempotent_write(
    session: Session,
    *,
    user_id: str,
    kind: str,
    idempotency_key: str,
    amount: int = 0,
    meta: Optional[dict] = None,
) -> UsageLedgerEntry:
    """Write a ledger entry idempotently. Returns existing entry if key already exists."""
    existing = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == idempotency_key)
    ).first()
    if existing:
        return existing

    entry = UsageLedgerEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        kind=kind,
        idempotency_key=idempotency_key,
        amount=amount,
        meta=meta,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    return entry


def reserve_run(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record a run reservation in the ledger."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="run_reservation",
        idempotency_key=f"run:{debate_id}",
        amount=1,
        meta={"debate_id": debate_id},
    )


def record_token_usage(
    session: Session,
    user_id: str,
    debate_id: str,
    attempt_id: Optional[str],
    tokens: int,
) -> UsageLedgerEntry:
    """Record token usage idempotently per attempt."""
    key = f"token_usage:{debate_id}:{attempt_id or 'initial'}"
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="token_usage",
        idempotency_key=key,
        amount=tokens,
        meta={"debate_id": debate_id, "attempt_id": attempt_id},
    )


def reserve_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record a hosted credit reservation."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="credit_reservation",
        idempotency_key=f"credit_reserve:{debate_id}",
        amount=1,
        meta={"debate_id": debate_id},
    )


def settle_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Mark credit settlement as complete (no-op if already settled)."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="credit_settlement",
        idempotency_key=f"credit_settle:{debate_id}",
        amount=0,
        meta={"debate_id": debate_id},
    )


def refund_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record a credit refund (idempotent — only one refund per debate)."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="credit_refund",
        idempotency_key=f"credit_refund:{debate_id}",
        amount=-1,
        meta={"debate_id": debate_id},
    )


def record_export(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record an export usage event."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="export",
        idempotency_key=f"export:{debate_id}:{uuid.uuid4().hex[:8]}",
        amount=1,
        meta={"debate_id": debate_id},
    )
