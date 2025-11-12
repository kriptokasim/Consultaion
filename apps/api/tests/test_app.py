import asyncio
import os
import sys
import tempfile
from pathlib import Path
import atexit

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlmodel import Session, select
from starlette.requests import Request

fd, temp_path = tempfile.mkstemp(prefix="consultaion_test_", suffix=".db")
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

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import engine, init_db  # noqa: E402
from main import (  # noqa: E402
    AuthRequest,
    DebateCreate,
    create_debate,
    export_scores_csv,
    get_debate,
    healthz,
    list_debates,
    register_user,
)
from models import Debate, Score, User  # noqa: E402
from orchestrator import run_debate  # noqa: E402
from schemas import default_debate_config  # noqa: E402

init_db()


def dummy_request(path: str = "/debates") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 0),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_health_endpoint_direct():
    result = healthz()
    assert result["ok"] is True


@pytest.mark.anyio
async def test_run_debate_emits_final_events():
    debate_id = "pytest-debate"
    with Session(engine) as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
            session.commit()
        session.add(
            Debate(
                id=debate_id,
                prompt="Pytest prompt",
                status="queued",
                config=default_debate_config().model_dump(),
            )
        )
        session.commit()

    q: asyncio.Queue = asyncio.Queue()
    await run_debate(debate_id, "Pytest prompt", q, default_debate_config().model_dump())

    events = []
    while not q.empty():
        events.append(await q.get())

    final_events = [event for event in events if event.get("type") == "final"]
    assert final_events, f"No final event emitted: {events}"
    meta = final_events[-1]["meta"]
    assert "ranking" in meta
    assert "usage" in meta


def _register_user(email: str, password: str) -> User:
    body = AuthRequest(email=email, password=password)
    with Session(engine) as session:
        response = Response()
        asyncio.run(register_user(body, response, session))
        user = session.exec(select(User).where(User.email == email.strip().lower())).first()
        return user


def _create_debate_for_user(user: User, prompt: str) -> str:
    background_tasks = BackgroundTasks()
    request = dummy_request()
    body = DebateCreate(prompt=prompt)
    with Session(engine) as session:
        result = asyncio.run(
            create_debate(
                body,
                background_tasks,
                request,
                session,
                current_user=user,
            )
        )
        return result["id"]


def test_export_scores_csv_endpoint():
    user = _register_user("csv@example.com", "secret123")
    debate_id = _create_debate_for_user(user, "CSV prompt")
    with Session(engine) as session:
        session.add(
            Score(
                debate_id=debate_id,
                persona="Analyst",
                judge="JudgeOne",
                score=8.5,
                rationale="Strong analysis",
            )
        )
        session.commit()
    with Session(engine) as session:
        csv_response = asyncio.run(
            export_scores_csv(
                debate_id,
                session=session,
                current_user=user,
            )
        )
    text = csv_response.body.decode()
    assert "persona,judge,score,rationale,timestamp" in text
    assert "Analyst" in text


def test_user_scoped_debates_and_admin_access():
    owner = _register_user("owner@example.com", "ownerpass")
    reviewer = _register_user("stranger@example.com", "strangepass")
    debate_id = _create_debate_for_user(owner, "Owner prompt")

    with Session(engine) as session:
        owner_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=owner)
        )
        assert any(item.id == debate_id for item in owner_runs)

    with Session(engine) as session:
        stranger_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=reviewer)
        )
        assert all(item.id != debate_id for item in stranger_runs)
        with pytest.raises(HTTPException):
            asyncio.run(get_debate(debate_id, session=session, current_user=reviewer))

    with Session(engine) as session:
        admin = session.get(User, reviewer.id)
        admin.role = "admin"
        session.add(admin)
        session.commit()

    with Session(engine) as session:
        admin_user = session.get(User, reviewer.id)
        admin_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=admin_user)
        )
        assert any(item.id == debate_id for item in admin_runs)
