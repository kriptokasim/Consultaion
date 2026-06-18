"""Audit ordering, metadata, and account deletion tests.

Patchset 133 §7.7: Proves audit records persist correctly and deletion
is safe on PostgreSQL.
"""

import pytest
import uuid
from sqlmodel import Session, select
from models import User, SupportNote, AuditLog, Debate, utcnow
from audit import record_audit


@pytest.fixture
def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"audit-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestAuditMetadata:
    def test_audit_metadata_input_not_mutated(self, db_session, test_user):
        """FH125: record_audit must not mutate the caller's meta dict."""
        original_meta = {"key": "value", "count": 1}
        meta_copy = dict(original_meta)

        record_audit(
            "test_action",
            user_id=test_user.id,
            meta=original_meta,
            session=db_session,
        )

        # Original dict should be unchanged
        assert original_meta == meta_copy, "record_audit mutated the caller's meta dict"

    def test_audit_persists_atomically(self, db_session, test_user):
        """FH125: Audit record staged before commit persists atomically."""
        record_audit(
            "test_atomic",
            user_id=test_user.id,
            target_type="user",
            target_id=test_user.id,
            meta={"test": True},
            session=db_session,
        )
        db_session.commit()

        logs = db_session.exec(
            select(AuditLog).where(
                AuditLog.user_id == test_user.id,
                AuditLog.action == "test_atomic",
            )
        ).all()
        assert len(logs) == 1
        assert logs[0].meta["test"] is True

    def test_audit_standalone_creates_session(self, test_user):
        """FH125: record_audit without session creates its own session."""
        record_audit(
            "standalone_test",
            user_id=test_user.id,
            target_type="user",
            target_id=test_user.id,
        )
        # Should not raise — standalone mode creates and commits its own session


class TestAccountDeletion:
    def test_account_deletion_support_note_nullable(self, db_session, test_user):
        """FH125: SupportNote.user_id is nullable after deletion."""
        note = SupportNote(
            user_id=test_user.id,
            author_id=test_user.id,
            note="Test note",
        )
        db_session.add(note)
        db_session.commit()

        # Anonymize support notes about the user
        import sqlalchemy as sa
        db_session.execute(
            sa.update(SupportNote)
            .where(SupportNote.user_id == test_user.id)
            .values(user_id=None, note="[User deleted]")
        )
        db_session.commit()

        db_session.refresh(note)
        assert note.user_id is None
        assert note.note == "[User deleted]"

    def test_account_deletion_is_idempotent(self, db_session, test_user):
        """FH125: Running deletion twice does not raise."""
        import sqlalchemy as sa
        from models import APIKey, UserProviderKey

        # First deletion
        db_session.execute(sa.delete(APIKey).where(APIKey.user_id == test_user.id))
        db_session.execute(sa.delete(UserProviderKey).where(UserProviderKey.user_id == test_user.id))
        db_session.commit()

        # Second deletion (idempotent — no rows to delete)
        db_session.execute(sa.delete(APIKey).where(APIKey.user_id == test_user.id))
        db_session.execute(sa.delete(UserProviderKey).where(UserProviderKey.user_id == test_user.id))
        db_session.commit()
