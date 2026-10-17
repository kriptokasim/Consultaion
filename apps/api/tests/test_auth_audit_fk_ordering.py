"""Signup paths must insert the user row before its audit_log row.

The shared test engine does not enforce SQLite foreign keys on pooled
connections, which is how PYTHON-FASTAPI-S (/auth/register 400) and
PYTHON-FASTAPI-10 (/auth/google/callback 500) reached production. These tests
use an engine that enforces them on every connection, like PostgreSQL.
"""

import asyncio
from unittest.mock import patch

import pytest
from exceptions import ValidationError
from fastapi import Response
from models import AuditLog, User
from schemas import AuthRequest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.requests import Request


@pytest.fixture()
def fk_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enforce_fks(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _request(method: str, path: str, headers=None) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": ("203.0.113.7", 0),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def _audit_rows(engine, action):
    with Session(engine) as session:
        return session.exec(select(AuditLog).where(AuditLog.action == action)).all()


def test_register_persists_user_and_audit_with_fks_enforced(fk_engine):
    from routes.auth import register_user

    with Session(fk_engine) as session:
        result = asyncio.run(
            register_user(
                body=AuthRequest(email="new-user@example.com", password="correct-horse-1"),
                request=_request("POST", "/auth/register"),
                response=Response(),
                session=session,
            )
        )

    assert result["email"] == "new-user@example.com"
    with Session(fk_engine) as session:
        user = session.exec(select(User).where(User.email == "new-user@example.com")).one()
    rows = _audit_rows(fk_engine, "register")
    assert [r.user_id for r in rows] == [user.id]


def test_register_duplicate_email_still_reports_email_exists(fk_engine):
    from routes.auth import register_user

    with Session(fk_engine) as session:
        session.add(User(email="taken@example.com", password_hash="x"))
        session.commit()

    with Session(fk_engine) as session, patch(
        "routes.auth.select", side_effect=lambda *_: select(User).where(User.email == "nobody")
    ):
        # Simulate the concurrent-signup race: the existence check misses, the
        # INSERT then hits the unique constraint.
        with pytest.raises(ValidationError) as exc:
            asyncio.run(
                register_user(
                    body=AuthRequest(email="taken@example.com", password="correct-horse-1"),
                    request=_request("POST", "/auth/register"),
                    response=Response(),
                    session=session,
                )
            )
    assert exc.value.code == "auth.email_exists"


def test_google_callback_new_user_with_fks_enforced(fk_engine, monkeypatch):
    import routes.auth as auth_routes

    async def _token(*_args):
        return {"access_token": "test-token"}

    async def _profile(_token):
        return {"email": "fresh-google@example.com"}

    monkeypatch.setattr(auth_routes.settings, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(auth_routes.settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(
        auth_routes.settings, "GOOGLE_REDIRECT_URL", "http://localhost:8000/auth/google/callback"
    )
    monkeypatch.setattr(auth_routes.settings, "RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(auth_routes.settings, "WEB_APP_ORIGIN", "http://localhost:3000")
    monkeypatch.setattr(auth_routes, "_exchange_code_for_token", _token)
    monkeypatch.setattr(auth_routes, "_fetch_google_profile", _profile)

    request = _request(
        "GET",
        "/auth/google/callback",
        headers=[(b"cookie", b"google_oauth_state=abc123; google_oauth_next=/dashboard")],
    )
    with patch(
        "security.state_store.state_store.consume_state",
        return_value={"next": "/dashboard", "created_at": 1, "ip": "203.0.113.7"},
    ), Session(fk_engine) as session:
        redirect = asyncio.run(
            auth_routes.google_callback(
                request=request,
                response=Response(),
                code="test-code",
                state="abc123",
                session=session,
            )
        )

    assert redirect.status_code in (302, 307)
    with Session(fk_engine) as session:
        user = session.exec(select(User).where(User.email == "fresh-google@example.com")).one()
    rows = _audit_rows(fk_engine, "register_google")
    assert [r.user_id for r in rows] == [user.id]
