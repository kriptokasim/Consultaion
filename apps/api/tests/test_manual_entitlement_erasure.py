from datetime import timedelta

from billing.manual_entitlements import grant_manual_entitlement
from billing.models import BillingSubscription
from models import User, utcnow
from services.account_erasure import erase_user_account
from sqlmodel import Session


def _user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="hashed", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_account_erasure_deletes_target_users_manual_entitlement(db_session: Session):
    target = _user(db_session, "manual-target@example.com")
    admin = _user(db_session, "manual-grantor@example.com")
    grant = grant_manual_entitlement(
        db_session,
        user_id=target.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="Support note containing user-specific context",
        expires_at=utcnow() + timedelta(days=7),
    )
    db_session.commit()
    grant_id = grant.id

    erase_user_account(db_session, target)
    db_session.commit()

    assert db_session.get(BillingSubscription, grant_id) is None


def test_erasing_granting_admin_detaches_admin_id_from_other_users_grant(db_session: Session):
    target = _user(db_session, "manual-other-user@example.com")
    admin = _user(db_session, "manual-admin-delete@example.com")
    grant = grant_manual_entitlement(
        db_session,
        user_id=target.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="Design partner access",
        expires_at=utcnow() + timedelta(days=7),
    )
    db_session.commit()
    grant_id = grant.id

    erase_user_account(db_session, admin)
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(BillingSubscription, grant_id)
    assert persisted is not None
    assert persisted.user_id == target.id
    assert persisted.granted_by_user_id is None
    assert persisted.entitlement_reason == "Design partner access"
