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
    # Patchset 73: Add IP address to meta if provided
    final_meta = meta or {}
    if ip_address:
        final_meta["ip_address"] = ip_address
    
    try:
        if session is None:
            with session_scope() as scoped:
                log = AuditLog(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    meta=final_meta,
                    created_at=utcnow(),
                )
                scoped.add(log)
        else:
            log = AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                meta=final_meta,
                created_at=utcnow(),
            )
            session.add(log)
            session.commit()
    except SQLAlchemyError:
        # Audit failures should never block primary flows.
        return
