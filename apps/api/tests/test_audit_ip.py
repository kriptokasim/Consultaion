
import uuid
from unittest.mock import MagicMock

from auth import hash_password
from fastapi import Request
from models import AuditLog, User
from routes.admin import UpdateUserStatusRequest, admin_update_user_status
from sqlmodel import Session, select


def test_audit_log_captures_ip(db_session: Session):
    # Setup admin and user
    admin = User(
        id=str(uuid.uuid4()),
        email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("StrongPass#1"),
        is_admin=True,
    )
    user = User(
        id=str(uuid.uuid4()),
        email=f"user-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("StrongPass#2"),
    )
    db_session.add(admin)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(user)

    # Mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "192.168.1.100"

    # Call admin action
    payload = UpdateUserStatusRequest(is_active=False)
    admin_update_user_status(
        user_id=user.id,
        request=payload,
        req=mock_request,
        session=db_session,
        admin=admin,
    )

    # Verify AuditLog
    log = db_session.exec(select(AuditLog).where(AuditLog.action == "account_disabled")).first()
    assert log is not None
    assert log.meta["ip_address"] == "192.168.1.100"
    assert log.meta["old_status"] is True  # Default is True
    assert log.meta["new_status"] is False
