import atexit
import os
import sys
import tempfile
import uuid
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

fd, temp_path = tempfile.mkstemp(prefix="consultaion_auth_flows_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("ENABLE_CSRF", "1")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["RL_MAX_CALLS"] = "1000"
os.environ["AUTH_RL_MAX_CALLS"] = "1000"
os.environ.setdefault("WEB_APP_ORIGIN", "http://localhost:3000")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URL", "http://testserver/auth/google/callback")
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import COOKIE_NAME, create_access_token, hash_password  # noqa: E402
from database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from models import User  # noqa: E402
from routes.auth import OAUTH_NEXT_COOKIE, OAUTH_STATE_COOKIE  # noqa: E402

init_db()

pytestmark = pytest.mark.anyio

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    if not token:
        return {}
    return {"X-CSRF-Token": token}


async def test_email_password_flow_sets_cookies(client: AsyncClient):
    email = f"user-{uuid.uuid4().hex[:6]}@example.com"
    payload = {"email": email, "password": "SecurePass123!"}
    res = await client.post("/auth/register", json=payload)
    assert res.status_code == 201
    assert res.json()["email"] == email
    assert client.cookies.get(COOKIE_NAME)
    assert client.cookies.get("csrf_token")

    res = await client.post("/auth/login", json=payload)
    assert res.status_code == 200
    assert client.cookies.get(COOKIE_NAME)
    assert client.cookies.get("csrf_token")

    me = await client.get("/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    bad = await client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401

    logout = await client.post("/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 200
    assert not client.cookies.get(COOKIE_NAME)


async def test_invalid_and_expired_tokens_rejected(client: AsyncClient):
    bogus = jwt.encode({"sub": "fake", "exp": 0}, "other-secret", algorithm="HS256")
    client.cookies.set(COOKIE_NAME, bogus, domain="testserver", path="/")
    res = await client.get("/me")
    assert res.status_code == 401

    with Session(engine) as session:
        user = User(id=str(uuid.uuid4()), email=f"expired-{uuid.uuid4().hex[:6]}@example.com", password_hash=hash_password("TestPass123"))
        session.add(user)
        session.commit()
        session.refresh(user)
    expired = create_access_token(user_id=user.id, email=user.email, role=user.role, ttl_seconds=-5)
    client.cookies.set(COOKIE_NAME, expired, domain="testserver", path="/")
    res = await client.get("/me")
    assert res.status_code == 401

    with Session(engine) as session:
        inactive = User(
            id=str(uuid.uuid4()),
            email=f"inactive-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("TestPass234"),
            is_active=False,
        )
        session.add(inactive)
        session.commit()
        session.refresh(inactive)
    token = create_access_token(user_id=inactive.id, email=inactive.email, role=inactive.role)
    client.cookies.set(COOKIE_NAME, token, domain="testserver", path="/")
    res = await client.get("/me")
    assert res.status_code in (401, 403)


async def test_google_login_sets_state_and_redirect(client: AsyncClient):
    res = await client.get("/auth/google/login?next=/dashboard", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert "accounts.google.com" in res.headers["location"]
    
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(res.headers["location"])
    qs = parse_qs(parsed.query)
    assert "state" in qs
    
    evil = await client.get("/auth/google/login?next=https://evil.example/phish", follow_redirects=False)
    assert evil.status_code in (302, 307)


async def test_google_callback_creates_user_and_sets_cookie(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_exchange(code: str, client_id: str, client_secret: str, redirect_url: str):
        return {"access_token": "token", "id_token": "ignored"}

    async def fake_profile(access_token: str):
        return {"email": f"google-{uuid.uuid4().hex[:6]}@example.com", "name": "G User"}

    import routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "_exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(auth_routes, "_fetch_google_profile", fake_profile)
    login = await client.get("/auth/google/login?next=/dashboard", follow_redirects=False)
    assert login.status_code in (302, 307)
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(login.headers["location"])
    qs = parse_qs(parsed.query)
    state = qs.get("state", [""])[0]
    assert state
    res = await client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert res.status_code in (302, 303, 307)
    # The new callback flow sets redirect URL token, not cookie
    assert "?token=" in res.headers["location"]


async def test_get_me_requires_cookie(client: AsyncClient):
    client.cookies.clear()
    res = await client.get("/me")
    assert res.status_code == 401
