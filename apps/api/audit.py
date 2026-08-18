from __future__ import annotations

from typing import Any, Optional

from database import session_scope
from models import AuditLog, utcnow
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

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
    - caller session has pending ORM mutations: stage the audit row in that same
      transaction so caller commit/rollback remains atomic;
    - caller session has no visible ORM mutations: persist the audit row through
      a standalone transaction and leave the caller session untouched.

    The last rule is intentionally conservative. ``session.new/dirty/deleted``
    cannot see every Core ``session.execute(UPDATE/DELETE/INSERT)`` mutation, so
    auto-committing a seemingly-clean caller session could accidentally commit
    business data. Audit code must never own that decision.

    Callers that require audit atomicity with Core DML should explicitly stage an
    ``AuditLog`` in their transaction (or use a dedicated future helper) rather
    than relying on implicit commit heuristics.
    """
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

        # Snapshot caller-owned ORM state before adding anything. If domain ORM
        # changes are pending, keep audit evidence in the caller transaction.
        has_pending_orm_changes = bool(session.new or session.dirty or session.deleted)
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

        # A clean ORM unit-of-work does NOT prove the transaction is read-only:
        # Core DML executed via session.execute() is invisible to the collections
        # above. Never commit/rollback the caller session here. Use an independent
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
    except SQLAlchemyError:
        # Audit failures must not commit, rollback, or poison caller-owned work.
        return
