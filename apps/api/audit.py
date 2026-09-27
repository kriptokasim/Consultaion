from __future__ import annotations

import logging
from typing import Any, Optional

from database import session_scope
from models import AuditLog, utcnow
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession
from sqlmodel import Session

logger = logging.getLogger(__name__)

# session.new/dirty/deleted are emptied by every flush, including autoflush,
# so they cannot tell record_audit whether the caller's transaction has
# already written. Track that on the session itself.
_TXN_HAS_WRITES = "audit_txn_has_writes"


@event.listens_for(OrmSession, "after_flush")
def _note_flushed_writes(session, _flush_context) -> None:
    session.info[_TXN_HAS_WRITES] = True


@event.listens_for(OrmSession, "do_orm_execute")
def _note_orm_dml(orm_execute_state) -> None:
    if orm_execute_state.is_insert or orm_execute_state.is_update or orm_execute_state.is_delete:
        orm_execute_state.session.info[_TXN_HAS_WRITES] = True


@event.listens_for(OrmSession, "after_transaction_end")
def _clear_txn_writes(session, transaction) -> None:
    if transaction.parent is None:
        session.info.pop(_TXN_HAS_WRITES, None)

# Public-share acquisition attribution is token-based. Retaining visitor IP on
# the generic public-view audit event no longer serves product attribution and
# adds unnecessary personal-data retention. Security/auth actions may still
# retain IP when their caller supplies it.
_IP_SUPPRESSED_ACTIONS = {"view_shared_debate"}


def _new_audit_log(
    action: str,
    *,
    user_id: Optional[str],
    target_type: Optional[str],
    target_id: Optional[str],
    meta: dict[str, Any],
) -> AuditLog:
    return AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta,
        created_at=utcnow(),
    )


def _audit_meta(
    action: str, ip_address: Optional[str], meta: Optional[dict[str, Any]]
) -> dict[str, Any]:
    final_meta = dict(meta or {})
    if ip_address and action not in _IP_SUPPRESSED_ACTIONS:
        final_meta["ip_address"] = ip_address
    else:
        # Central policy also protects against a caller placing the same field
        # directly in meta for a public-view event.
        final_meta.pop("ip_address", None)
        if action in _IP_SUPPRESSED_ACTIONS:
            final_meta.pop("client_ip", None)
            final_meta.pop("remote_addr", None)
    return final_meta


def stage_audit(
    session: Session,
    action: str,
    *,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    """Add an audit row to the caller's transaction unconditionally.

    Use when the audit row must commit or roll back with the caller's work, in
    particular when it references a row the caller has only flushed: a
    standalone audit transaction cannot see that row and fails its FK.
    """
    session.add(
        _new_audit_log(
            action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            meta=_audit_meta(action, ip_address, meta),
        )
    )


def record_audit(
    action: str,
    *,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> None:
    """Record a best-effort audit event without committing caller-owned work.

    Transaction contract:
    - no session supplied: persist in a standalone committed transaction;
    - caller session has pending or flushed-but-uncommitted ORM writes (including
      ORM-level ``session.execute(update(...))``): stage the audit row in that
      same transaction so caller commit/rollback remains atomic;
    - otherwise: persist the audit row through a standalone transaction and
      leave the caller session untouched.

    The last rule is intentionally conservative: textual SQL run through
    ``session.execute(text(...))`` is not detected, so auto-committing a
    seemingly-clean caller session could accidentally commit business data.
    Audit code must never own that decision.

    Callers that require audit atomicity with Core DML should explicitly stage an
    ``AuditLog`` in their transaction (or use a dedicated future helper) rather
    than relying on implicit commit heuristics.
    """
    final_meta = _audit_meta(action, ip_address, meta)

    # Snapshot caller-owned state before adding anything. If the caller's
    # transaction has pending or already-flushed writes, keep audit evidence in
    # that transaction so it commits or rolls back with them.
    has_unflushed_changes = session is not None and bool(
        session.new or session.dirty or session.deleted
    )
    has_pending_orm_changes = has_unflushed_changes or (
        session is not None and session.info.get(_TXN_HAS_WRITES) is True
    )
    if has_unflushed_changes:
        # The ORM does not order the audit INSERT after a pending row it
        # references (e.g. a new user), so flush the caller's work first.
        # Outside the try: a failure here is the caller's, not the audit's.
        session.flush()

    try:
        if session is None:
            with session_scope() as scoped:
                scoped.add(
                    _new_audit_log(
                        action,
                        user_id=user_id,
                        target_type=target_type,
                        target_id=target_id,
                        meta=final_meta,
                    )
                )
            return

        if has_pending_orm_changes:
            session.add(
                _new_audit_log(
                    action,
                    user_id=user_id,
                    target_type=target_type,
                    target_id=target_id,
                    meta=final_meta,
                )
            )
            return

        # Textual SQL run through session.execute() is still invisible here, so
        # never commit/rollback the caller session. Use an independent
        # best-effort audit transaction instead.
        with session_scope() as scoped:
            scoped.add(
                _new_audit_log(
                    action,
                    user_id=user_id,
                    target_type=target_type,
                    target_id=target_id,
                    meta=final_meta,
                )
            )
    except SQLAlchemyError as exc:
        # Audit failures must not commit, rollback, or poison caller-owned work,
        # but they must never be silent: a dropped row is missing security
        # evidence, not a no-op.
        logger.error(
            "Failed to record audit event %s (target=%s/%s): %s",
            action,
            target_type,
            target_id,
            exc,
        )
        return
