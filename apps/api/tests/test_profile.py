import atexit
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, select

fd, temp_path = tempfile.mkstemp(prefix="consultaion_profile_", suffix=".db")
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
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["RL_MAX_CALLS"] = "1000"
os.environ["AUTH_RL_MAX_CALLS"] = "1000"
os.environ.setdefault("FASTAPI_TEST_MODE", "1")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import config as config_module  # noqa: E402
config_module.settings.reload()

import database  # noqa: E402
database.reset_engine()
from database import init_db  # noqa: E402
from main import app  # noqa: E402
from models import User  # noqa: E402

# Create tables after models are loaded
init_db()


pytestmark = pytest.mark.anyio

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def _register_and_login(client: AsyncClient, email: str, password: str) -> None:
    await client.post("/auth/register", json={"email": email, "password": password})
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200


async def test_profile_read_write_happy_path(client: AsyncClient):
    email = f"profile-{uuid.uuid4().hex[:6]}@example.com"
    await _register_and_login(client, email, "ProfilePass123!")

    res = await client.get("/me/profile")
    assert res.status_code == 200
    payload = res.json()
    assert payload["email"] == email

    update = {
        "display_name": "  Amber  ",
        "avatar_url": " https://example.com/avatar.png ",
        "bio": "Amber mocha pilot",
        "timezone": "Europe/Istanbul",
    }
    updated = await client.put("/me/profile", json=update, headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")})
    assert updated.status_code == 200
    data = updated.json()
    assert data["display_name"] == "Amber"
    assert data["avatar_url"] == "https://example.com/avatar.png"
    assert data["timezone"] == "Europe/Istanbul"

    if os.getenv("FASTAPI_TEST_MODE") != "1":
        with Session(database.engine) as session:
            user = session.exec(select(User).where(User.email == email)).first()
            assert user.display_name == "Amber"
        assert user.timezone == "Europe/Istanbul"


async def test_profile_requires_auth(client: AsyncClient):
    client.cookies.clear()
    res = await client.get("/me/profile")
    assert res.status_code == 401
    client.cookies.set("csrf_token", "fake", domain="testserver", path="/")
    res = await client.put("/me/profile", json={"display_name": "Nope"}, headers={"X-CSRF-Token": "fake"})
    assert res.status_code == 401


async def test_profile_validation_errors(client: AsyncClient):
    email = f"profile-err-{uuid.uuid4().hex[:6]}@example.com"
    await _register_and_login(client, email, "ProfileValidate123!")
    too_long = "x" * 2000
    res = await client.put(
        "/me/profile",
        json={"bio": too_long},
        headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")},
    )
    assert res.status_code == 422
