import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from models import Team, TeamMember
from routes import teams
from sqlalchemy.exc import IntegrityError


def test_create_team_stages_owner_before_single_commit(monkeypatch):
    class FailingSession:
        def __init__(self):
            self.added = []
            self.commit_calls = 0
            self.rollback_called = False

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.commit_calls += 1
            assert any(isinstance(obj, Team) for obj in self.added)
            assert any(isinstance(obj, TeamMember) for obj in self.added)
            raise IntegrityError("insert team owner", {}, Exception("forced failure"))

        def rollback(self):
            self.rollback_called = True

        def refresh(self, _obj):  # pragma: no cover - commit fails first
            raise AssertionError("refresh must not run after failed commit")

    session = FailingSession()
    user = SimpleNamespace(id="user-atomic")

    audit_calls = []

    def fake_record_audit(*args, **kwargs):
        audit_calls.append((args, kwargs))
        assert kwargs["session"] is session

    monkeypatch.setattr(teams, "record_audit", fake_record_audit)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            teams.create_team(
                teams.TeamCreate(name="Atomic Team"),
                session=session,
                current_user=user,
            )
        )

    assert exc.value.status_code == 409
    assert session.commit_calls == 1
    assert session.rollback_called is True
    assert len(audit_calls) == 1
