import uuid

from models import AuditLog, Debate, DebateAttempt, Message, User
from services.account_erasure import erase_user_account
from sqlmodel import Session, select


def test_account_erasure_preserves_attempt_fk_and_scrubs_targeted_admin_audit(
    db_session: Session,
):
    user = User(
        id=str(uuid.uuid4()),
        email=f"erase-target-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        plan="free",
        is_active=True,
    )
    admin = User(
        id=str(uuid.uuid4()),
        email=f"erase-admin-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        plan="free",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.add(admin)
    db_session.commit()

    original_email = user.email
    debate = Debate(
        id=f"erase-debate-{uuid.uuid4().hex}",
        prompt="Sensitive account-erasure prompt",
        status="completed",
        user_id=user.id,
        config={},
    )
    db_session.add(debate)
    db_session.flush()

    attempt = DebateAttempt(
        debate_id=debate.id,
        attempt_number=1,
        status="completed",
        error_summary="Sensitive attempt diagnostic",
        meta={"private": "attempt metadata"},
    )
    db_session.add(attempt)
    db_session.flush()
    db_session.add(
        Message(
            debate_id=debate.id,
            attempt_id=attempt.id,
            round_index=0,
            role="arena_response",
            content="Sensitive model output",
            meta={"private": "message metadata"},
        )
    )
    db_session.add(
        AuditLog(
            user_id=admin.id,
            action="plan_changed",
            target_type="user",
            target_id=user.id,
            meta={
                "target_email": original_email,
                "client_ip": "203.0.113.10",
                "nested": {"user_email": original_email},
                "safe_fact": "pro-to-free",
            },
        )
    )
    db_session.commit()

    erase_user_account(db_session, user)
    db_session.commit()
    db_session.expire_all()

    kept_attempt = db_session.exec(
        select(DebateAttempt).where(DebateAttempt.debate_id == debate.id)
    ).first()
    assert kept_attempt is not None
    assert kept_attempt.error_summary is None
    assert kept_attempt.meta is None

    kept_message = db_session.exec(
        select(Message).where(Message.debate_id == debate.id)
    ).first()
    assert kept_message is not None
    assert kept_message.attempt_id == kept_attempt.id
    assert kept_message.content == "[DELETED]"
    assert kept_message.meta is None

    targeted_audit = db_session.exec(
        select(AuditLog)
        .where(AuditLog.action == "plan_changed")
        .where(AuditLog.target_id == user.id)
    ).first()
    assert targeted_audit is not None
    assert targeted_audit.user_id == admin.id
    assert targeted_audit.meta["target_email"] == "[REDACTED]"
    assert targeted_audit.meta["client_ip"] == "[REDACTED]"
    assert targeted_audit.meta["nested"]["user_email"] == "[REDACTED]"
    assert targeted_audit.meta["safe_fact"] == "pro-to-free"
    assert original_email not in str(targeted_audit.meta)
