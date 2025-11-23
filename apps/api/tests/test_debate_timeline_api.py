import atexit
import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

fd, temp_path = tempfile.mkstemp(prefix="consultaion_timeline_api_", suffix=".db")
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

import importlib
import config as config_module
importlib.reload(config_module)

from auth import COOKIE_NAME, hash_password  # noqa: E402
from database import engine, init_db, reset_engine  # noqa: E402
from main import app  # noqa: E402
from models import Debate, Message, User  # noqa: E402
from schemas import default_panel_config  # noqa: E402

reset_engine()
init_db()

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def _login(client: AsyncClient) -> User:
    with Session(engine) as session:
        user = User(email="timeline@example.com", password_hash=hash_password("StrongPass123!"))
        session.add(user)
        session.commit()
        session.refresh(user)
    res = await client.post("/auth/login", json={"email": user.email, "password": "StrongPass123!"})
    assert res.status_code == 200
    assert client.cookies.get(COOKIE_NAME)
    return user


async def test_get_timeline_requires_auth(client: AsyncClient):
    res = await client.get("/debates/123/timeline")
    assert res.status_code in (401, 403)


async def test_get_timeline_returns_events_for_completed_debate(client: AsyncClient):
    user = await _login(client)
    panel = default_panel_config()
    debate_id = "timeline-api"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Timeline api test",
            status="completed",
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
            user_id=user.id,
        )
        session.add(debate)
        session.commit()
        for idx, seat in enumerate(panel.seats):
            session.add(
                Message(
                    debate_id=debate_id,
                    round_index=idx,
                    role="seat",
                    persona=seat.display_name,
                    content="hello",
                    meta={"seat_id": seat.seat_id, "role_profile": seat.role_profile, "phase": "explore"},
                )
            )
        session.commit()

    res = await client.get(f"/debates/{debate_id}/timeline")
    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload, list)
    assert payload and payload[0]["event_type"] == "seat_message"


async def test_timeline_409_when_running(client: AsyncClient):
    user = await _login(client)
    panel = default_panel_config()
    debate_id = "timeline-running"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Timeline running",
            status="running",
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
            user_id=user.id,
        )
        session.add(debate)
        session.commit()
    res = await client.get(f"/debates/{debate_id}/timeline")
    assert res.status_code == 409
