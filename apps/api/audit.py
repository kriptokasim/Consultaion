from __future__ import annotations

from typing import Any, Optional

from database import session_scope
from models import AuditLog, utcnow
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session


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
    """Record an audit event without compromising the caller's transaction.

    Transaction contract:
    - no session supplied: use a standalone committed transaction;
    - caller session has pending domain mutations: stage the audit row and let
      the caller commit/rollback both atomically;
    - caller session is clean (the common post-commit call-site pattern): commit
      the audit-only row immediately so request teardown cannot discard it.

    This preserves atomicity for mutation-time audit events while preventing the
    historical silent loss of post-commit telemetry.
    """
    final_meta = dict(meta or {})
    if ip_address:
        final_meta["ip_address"] = ip_address

    try:
        if session is None:
            with session_scope() as scoped:
                scoped.add(
                    AuditLog(
                        user_id=user_id,
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        meta=final_meta,
                        created_at=utcnow(),
                    )
                )
            return

        # Snapshot caller-owned pending state *before* adding the audit row.
        # If anything is pending, the audit must stay in the same transaction.
        has_pending_domain_changes = bool(session.new or session.dirty or session.deleted)

        session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                meta=final_meta,
                created_at=utcnow(),
            )
        )

        if not has_pending_domain_changes:
            try:
                session.commit()
            except SQLAlchemyError:
                # We own this audit-only transaction. Reset the failed session so
                # a best-effort audit failure does not poison the request session.
                session.rollback()
                return
    except SQLAlchemyError:
        # Audit failures should never block primary flows.
        return
