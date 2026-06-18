"""Usage Ledger Service — idempotent accounting with state machine transitions.

Patchset 133 §6.11: Coherent operation model with valid transitions.

State machine:
  reserved → settled   (operation completed successfully)
  reserved → refunded  (operation cancelled/failed, credit returned)
  reserved → failed    (operation failed permanently)

Invalid transitions are rejected. Idempotency keys are deterministic.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from models import UsageLedgerEntry

logger = logging.getLogger(__name__)

# Valid state transitions
_VALID_TRANSITIONS = {
    "reserved": {"settled", "refunded", "failed"},
    "settled": set(),      # Terminal state
    "refunded": set(),     # Terminal state
    "failed": set(),       # Terminal state
}


class LedgerTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, current: str, target: str):
        super().__init__(f"Invalid ledger transition: {current} → {target}")
        self.current = current
        self.target = target


def _idempotent_write(
    session: Session,
    *,
    user_id: str,
    kind: str,
    idempotency_key: str,
    amount: int = 0,
    debate_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
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
        status="reserved",
        idempotency_key=idempotency_key,
        amount=amount,
        debate_id=debate_id,
        attempt_id=attempt_id,
        meta=meta,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    session.flush()
    return entry


def _transition(
    session: Session,
    entry: UsageLedgerEntry,
    target_status: str,
) -> UsageLedgerEntry:
    """Transition a ledger entry to a new status. Raises on invalid transition."""
    if target_status not in _VALID_TRANSITIONS.get(entry.status, set()):
        raise LedgerTransitionError(entry.status, target_status)

    entry.status = target_status
    now = datetime.now(timezone.utc)
    if target_status == "settled":
        entry.settled_at = now
    elif target_status == "refunded":
        entry.refunded_at = now
    session.add(entry)
    session.flush()
    return entry


def reserve_run(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record a run reservation in the ledger."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="run_reservation",
        idempotency_key=f"run:{debate_id}",
        amount=1,
        debate_id=debate_id,
    )


def settle_run(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Settle a run reservation (operation completed)."""
    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == f"run:{debate_id}")
    ).first()
    if not entry:
        raise ValueError(f"No reservation found for debate {debate_id}")
    return _transition(session, entry, "settled")


def refund_run(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Refund a run reservation (operation failed/cancelled)."""
    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == f"run:{debate_id}")
    ).first()
    if not entry:
        raise ValueError(f"No reservation found for debate {debate_id}")
    return _transition(session, entry, "refunded")


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
        debate_id=debate_id,
        attempt_id=attempt_id,
    )


def settle_token_usage(
    session: Session,
    user_id: str,
    debate_id: str,
    attempt_id: Optional[str],
) -> UsageLedgerEntry:
    """Settle token usage after operation completes."""
    key = f"token_usage:{debate_id}:{attempt_id or 'initial'}"
    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == key)
    ).first()
    if not entry:
        raise ValueError(f"No token usage found for debate {debate_id} attempt {attempt_id}")
    return _transition(session, entry, "settled")


def record_export(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record an export usage event.

    FH125: Idempotency key is deterministic — repeated delivery of the same
    export request will not double-charge.
    """
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="export",
        idempotency_key=f"export:{user_id}:{debate_id}",
        amount=1,
        debate_id=debate_id,
    )


def reserve_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Record a hosted credit reservation."""
    return _idempotent_write(
        session,
        user_id=user_id,
        kind="credit_reservation",
        idempotency_key=f"credit_reserve:{debate_id}",
        amount=1,
        debate_id=debate_id,
    )


def settle_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Settle hosted credit after operation completes."""
    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == f"credit_reserve:{debate_id}")
    ).first()
    if not entry:
        raise ValueError(f"No credit reservation found for debate {debate_id}")
    return _transition(session, entry, "settled")


def refund_hosted_credit(session: Session, user_id: str, debate_id: str) -> UsageLedgerEntry:
    """Refund hosted credit (operation failed/cancelled)."""
    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == f"credit_reserve:{debate_id}")
    ).first()
    if not entry:
        raise ValueError(f"No credit reservation found for debate {debate_id}")
    return _transition(session, entry, "refunded")
