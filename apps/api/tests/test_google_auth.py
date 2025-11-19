import asyncio
import os
import sys
import tempfile
import atexit
from pathlib import Path

from fastapi import Response
from sqlmodel import Session, select
from starlette.requests import Request

sys.path.append(str(Path(__file__).resolve().parents[1]))

fd, temp_path = tempfile.mkstemp(prefix="consultaion_google_test_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("DISABLE_AUTORUN", "1")
os.environ.setdefault("DISABLE_RATINGS", "1")
os.environ.setdefault("FAST_DEBATE", "1")
os.environ.setdefault("RL_MAX_CALLS", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_MAX_RUNS_PER_HOUR", "50")
os.environ.setdefault("DEFAULT_MAX_TOKENS_PER_DAY", "150000")

from main import app  # noqa: E402
from models import User  # noqa: E402
from database import engine, init_db  # noqa: E402
from routes.auth import google_callback, sanitize_next_path  # noqa: E402


async def _fake_exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_url: str):
    return {"access_token": "test-token", "id_token": "ignored"}


async def _fake_fetch_google_profile(access_token: str):
    return {"email": "google-user@example.com", "name": "Google User"}


def _build_request() -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/auth/google/callback",
        "raw_path": b"/auth/google/callback",
        "query_string": b"",
        "headers": [(b"cookie", b"google_oauth_state=abc123; google_oauth_next=/dashboard")],
        "client": ("testclient", 0),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_google_callback_creates_user(monkeypatch):
    init_db()
    import routes.auth as auth_routes

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URL", "http://localhost:8000/auth/google/callback")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")

    monkeypatch.setattr(auth_routes, "_exchange_code_for_token", _fake_exchange_code_for_token)
    monkeypatch.setattr(auth_routes, "_fetch_google_profile", _fake_fetch_google_profile)
    monkeypatch.setattr(auth_routes, "increment_ip_bucket", lambda *args, **kwargs: True)

    request = _build_request()
    response = Response()
    with Session(engine) as session:
        redirect_response = asyncio.run(
            google_callback(
                request=request,
                response=response,
                code="test-code",
                state="abc123",
                session=session,
            )
        )
    assert redirect_response.status_code in (302, 307)
    assert redirect_response.headers["location"] == "/dashboard"

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "google-user@example.com")).first()
        assert user is not None


def test_sanitize_next_path_allows_dashboard():
    assert sanitize_next_path("/dashboard?view=team") == "/dashboard?view=team"


def test_sanitize_next_path_rejects_absolute_urls():
    assert sanitize_next_path("https://evil.tld/phish") == "/dashboard"
