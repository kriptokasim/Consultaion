import asyncio
import importlib
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
os.environ.setdefault("DISABLE_RATINGS", "1")
os.environ.setdefault("FAST_DEBATE", "1")
os.environ.setdefault("RL_MAX_CALLS", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_MAX_RUNS_PER_HOUR", "50")
os.environ.setdefault("DEFAULT_MAX_TOKENS_PER_DAY", "150000")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import engine, init_db  # noqa: E402
from main import (  # noqa: E402
    AuthRequest,
    CHANNELS,
    CHANNEL_META,
    CHANNEL_TTL_SECS,
    DebateCreate,
    DebateUpdate,
    TeamCreate,
    TeamMemberCreate,
    add_team_member,
    admin_logs,
    create_debate,
    create_team,
    export_scores_csv,
    get_debate,
    get_leaderboard,
    healthz,
    list_debates,
    register_user,
    start_debate_run,
    sweep_stale_channels,
    update_debate,
)
from models import AuditLog, Debate, RatingPersona, Score, User  # noqa: E402
import orchestrator as orchestrator_module  # noqa: E402
from orchestrator import run_debate  # noqa: E402
from ratings import update_ratings_for_debate, wilson_interval  # noqa: E402
from schemas import default_debate_config  # noqa: E402

init_db()


def test_debate_create_prompt_validation():
    with pytest.raises(ValueError):
        DebateCreate(prompt=" too short ")
    with pytest.raises(ValueError):
        DebateCreate(prompt="x" * 6001)
    result = DebateCreate(prompt=" " * 2 + "valid prompt text" + " ")
    assert result.prompt == "valid prompt text"


def test_jwt_secret_default_rejected(monkeypatch):
    import auth as auth_module

    monkeypatch.setenv("JWT_SECRET", "change_me_in_prod")
    with pytest.raises(RuntimeError):
        importlib.reload(auth_module)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    importlib.reload(auth_module)


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


def test_health_endpoint_direct():
    result = healthz()
    assert result["ok"] is True


def test_run_debate_emits_final_events():
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
    asyncio.run(run_debate(debate_id, "Pytest prompt", q, default_debate_config().model_dump()))

    events = []
    while not q.empty():
        events.append(q.get_nowait())

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


def _create_team_for_user(owner: User, name: str = "Sepia Team") -> str:
    with Session(engine) as session:
        payload = TeamCreate(name=name)
        team_info = asyncio.run(create_team(payload, session=session, current_user=owner))
        return team_info["id"]


def _add_user_to_team(inviter: User, team_id: str, email: str, role: str = "viewer") -> None:
    with Session(engine) as session:
        payload = TeamMemberCreate(email=email, role=role)
        asyncio.run(add_team_member(team_id, payload, session=session, current_user=inviter))


def _assign_debate_to_team(actor: User, debate_id: str, team_id: str | None) -> None:
    with Session(engine) as session:
        payload = DebateUpdate(team_id=team_id)
        asyncio.run(update_debate(debate_id, payload, session=session, current_user=actor))


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
        assert any(item.id == debate_id for item in owner_runs["items"])

    with Session(engine) as session:
        stranger_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=reviewer)
        )
        assert all(item.id != debate_id for item in stranger_runs["items"])
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
        assert any(item.id == debate_id for item in admin_runs["items"])


def test_list_debates_returns_metadata():
    user = _register_user("pagination@example.com", "paginate")
    first = _create_debate_for_user(user, "Pagination prompt alpha")
    second = _create_debate_for_user(user, "Pagination prompt beta")
    assert first != second
    with Session(engine) as session:
        payload = asyncio.run(
            list_debates(None, 1, 0, session=session, current_user=user)
        )
    assert "items" in payload and "total" in payload
    assert payload["total"] >= 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert isinstance(payload["has_more"], bool)


def test_rate_limit_blocks_after_threshold():
    previous = os.environ.get("DEFAULT_MAX_RUNS_PER_HOUR", "50")
    os.environ["DEFAULT_MAX_RUNS_PER_HOUR"] = "1"
    user = _register_user("ratelimit@example.com", "securepass")
    _create_debate_for_user(user, "First allowed run")
    with pytest.raises(HTTPException) as exc_info:
        _create_debate_for_user(user, "Second run should fail")
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "rate_limit"
    with Session(engine) as session:
        logs = session.exec(
            select(AuditLog).where(AuditLog.action == "rate_limit_block", AuditLog.user_id == user.id)
        ).all()
        assert logs
    os.environ["DEFAULT_MAX_RUNS_PER_HOUR"] = previous


def test_admin_logs_endpoint_lists_entries():
    owner = _register_user("auditor@example.com", "ownerpass")
    _create_debate_for_user(owner, "Audit trail run")
    with Session(engine) as session:
        admin = session.get(User, owner.id)
        admin.role = "admin"
        session.add(admin)
        session.commit()
    with Session(engine) as session:
        admin_user = session.get(User, owner.id)
        payload = asyncio.run(admin_logs(50, session, admin_user))
    assert payload["items"]
    assert any(entry["action"] == "debate_created" for entry in payload["items"])


def test_wilson_interval_bounds():
    low, high = wilson_interval(8, 10)
    assert 0.4 < low < high < 1.0


def test_leaderboard_updates_after_score_entries():
    user = _register_user("elo@example.com", "elo-pass")
    debate_id = _create_debate_for_user(user, "Leaderboard prompt")
    with Session(engine) as session:
        debate = session.get(Debate, debate_id)
        debate.final_meta = {"category": "policy"}
        session.add(debate)
        session.add(
            Score(
                debate_id=debate_id,
                persona="Analyst",
                judge="JudgeOne",
                score=9.0,
                rationale="Great",
            )
        )
        session.add(
            Score(
                debate_id=debate_id,
                persona="Builder",
                judge="JudgeOne",
                score=7.0,
                rationale="Solid",
            )
        )
        session.commit()
    previous = os.environ.get("DISABLE_RATINGS", "1")
    os.environ["DISABLE_RATINGS"] = "0"
    update_ratings_for_debate(debate_id)
    os.environ["DISABLE_RATINGS"] = previous
    with Session(engine) as session:
        ratings = session.exec(select(RatingPersona).where(RatingPersona.persona == "Analyst")).all()
        assert ratings
        leaderboard = asyncio.run(get_leaderboard(None, 0, 10, session))
    assert any(entry["persona"] == "Analyst" for entry in leaderboard["items"])


def test_manual_start_requires_flag():
    previous = os.environ.get("DISABLE_AUTORUN", "1")
    os.environ["DISABLE_AUTORUN"] = "0"
    user = _register_user("manual-guard@example.com", "manualpass")
    debate_id = _create_debate_for_user(user, "Manual guard prompt")
    with Session(engine) as session:
        background_tasks = BackgroundTasks()
        with pytest.raises(HTTPException):
            asyncio.run(
                start_debate_run(
                    debate_id,
                    background_tasks,
                    session=session,
                    current_user=user,
                )
            )
    os.environ["DISABLE_AUTORUN"] = previous


def test_manual_start_succeeds_when_disabled():
    previous = os.environ.get("DISABLE_AUTORUN", "1")
    os.environ["DISABLE_AUTORUN"] = "1"
    user = _register_user("manual-ok@example.com", "manualpass")
    debate_id = _create_debate_for_user(user, "Manual start run prompt")
    with Session(engine) as session:
        background_tasks = BackgroundTasks()
        result = asyncio.run(
            start_debate_run(
                debate_id,
                background_tasks,
                session=session,
                current_user=user,
            )
        )
    assert result["status"] == "scheduled"
    assert debate_id in CHANNELS
    os.environ["DISABLE_AUTORUN"] = previous
    CHANNELS.pop(debate_id, None)
    CHANNEL_META.pop(debate_id, None)


def test_channel_sweeper_removes_stale_entries():
    CHANNELS["stale-test"] = asyncio.Queue()
    CHANNEL_META["stale-test"] = 0.0
    removed = sweep_stale_channels(now=CHANNEL_TTL_SECS + 5)
    assert "stale-test" in removed
    assert "stale-test" not in CHANNELS
    start_debate_run,
    sweep_stale_channels,
