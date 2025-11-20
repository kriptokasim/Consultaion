import atexit
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
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

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from models import User  # noqa: E402

init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(client: TestClient, email: str, password: str) -> None:
    client.post("/auth/register", json={"email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200


def test_profile_read_write_happy_path(client: TestClient):
    email = f"profile-{uuid.uuid4().hex[:6]}@example.com"
    _register_and_login(client, email, "ProfilePass123!")

    res = client.get("/me/profile")
    assert res.status_code == 200
    payload = res.json()
    assert payload["email"] == email

    update = {
        "display_name": "  Amber  ",
        "avatar_url": " https://example.com/avatar.png ",
        "bio": "Amber mocha pilot",
        "timezone": "Europe/Istanbul",
    }
    updated = client.put("/me/profile", json=update, headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")})
    assert updated.status_code == 200
    data = updated.json()
    assert data["display_name"] == "Amber"
    assert data["avatar_url"] == "https://example.com/avatar.png"
    assert data["timezone"] == "Europe/Istanbul"

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        assert user.display_name == "Amber"
        assert user.timezone == "Europe/Istanbul"


def test_profile_requires_auth(client: TestClient):
    client.cookies.clear()
    res = client.get("/me/profile")
    assert res.status_code == 401
    client.cookies.set("csrf_token", "fake", domain="testserver", path="/")
    res = client.put("/me/profile", json={"display_name": "Nope"}, headers={"X-CSRF-Token": "fake"})
    assert res.status_code == 403


def test_profile_validation_errors(client: TestClient):
    email = f"profile-err-{uuid.uuid4().hex[:6]}@example.com"
    _register_and_login(client, email, "ProfileValidate123!")
    too_long = "x" * 2000
    res = client.put(
        "/me/profile",
        json={"bio": too_long},
        headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")},
    )
    assert res.status_code == 422
