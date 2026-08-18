from audit import record_audit
from models import AuditLog, User
from sqlmodel import Session, select


def test_public_view_audit_drops_ip_but_auth_audit_can_retain_it(db_session: Session):
    user = User(
        email="audit-ip-policy@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db_session.add(user)

    record_audit(
        "view_shared_debate",
        user_id=None,
        target_type="debate",
        target_id="public-run-1",
        ip_address="203.0.113.10",
        meta={
            "ip_address": "203.0.113.11",
            "client_ip": "203.0.113.12",
            "remote_addr": "203.0.113.13",
            "safe_fact": "public_view",
        },
        session=db_session,
    )
    db_session.commit()

    public_log = db_session.exec(
        select(AuditLog).where(AuditLog.action == "view_shared_debate")
    ).first()
    assert public_log is not None
    assert public_log.meta.get("safe_fact") == "public_view"
    assert "ip_address" not in public_log.meta
    assert "client_ip" not in public_log.meta
    assert "remote_addr" not in public_log.meta

    # The policy is action-specific: authentication/security audit evidence can
    # still retain IP when a caller intentionally supplies it.
    user.display_name = "Updated"
    db_session.add(user)
    record_audit(
        "login",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address="203.0.113.20",
        session=db_session,
    )
    db_session.commit()

    login_log = db_session.exec(
        select(AuditLog).where(AuditLog.action == "login")
    ).first()
    assert login_log is not None
    assert login_log.meta.get("ip_address") == "203.0.113.20"
