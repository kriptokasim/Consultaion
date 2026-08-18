from unittest.mock import MagicMock, patch

import database
from audit import record_audit
from models import AuditLog, User
from sqlmodel import Session, select


def test_record_audit_persists_when_caller_session_is_clean(db_session: Session):
    record_audit(
        "post_commit_event",
        target_type="test",
        target_id="clean-session",
        session=db_session,
    )

    # Read the engine dynamically. Tests reset database.engine between cases;
    # importing the engine object at module import time would leave this test
    # attached to the pre-reset SQLite database.
    with Session(database.engine) as observer:
        row = observer.exec(
            select(AuditLog)
            .where(AuditLog.action == "post_commit_event")
            .where(AuditLog.target_id == "clean-session")
        ).first()

    assert row is not None


def test_record_audit_preserves_atomicity_with_pending_domain_changes(db_session: Session):
    user = User(
        email="audit-atomicity@example.com",
        password_hash="not-used-in-this-test",
    )
    db_session.add(user)

    record_audit(
        "atomic_event",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        session=db_session,
    )

    # A second session must not observe either row until the caller commits.
    with Session(database.engine) as observer:
        assert observer.exec(select(User).where(User.id == user.id)).first() is None
        assert observer.exec(
            select(AuditLog).where(AuditLog.action == "atomic_event")
        ).first() is None

    db_session.commit()

    with Session(database.engine) as observer:
        persisted_user = observer.exec(select(User).where(User.id == user.id)).first()
        persisted_audit = observer.exec(
            select(AuditLog).where(AuditLog.action == "atomic_event")
        ).first()

    assert persisted_user is not None
    assert persisted_audit is not None


def test_record_audit_never_commits_seemingly_clean_caller_session():
    """Core DML can be pending even when ORM new/dirty/deleted are empty."""
    caller = MagicMock()
    caller.new = set()
    caller.dirty = set()
    caller.deleted = set()

    standalone = MagicMock()
    scope = MagicMock()
    scope.__enter__.return_value = standalone
    scope.__exit__.return_value = False

    with patch("audit.session_scope", return_value=scope):
        record_audit(
            "core_dml_safety",
            target_type="test",
            target_id="caller-must-not-commit",
            session=caller,
        )

    caller.commit.assert_not_called()
    caller.rollback.assert_not_called()
    caller.add.assert_not_called()
    standalone.add.assert_called_once()
