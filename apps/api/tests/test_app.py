import asyncio
import importlib
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlmodel import Session, select
from starlette.requests import Request

sys.path.append(str(Path(__file__).resolve().parents[1]))

import config as config_module  # noqa: E402
from config import settings  # noqa: E402
from tests.utils import settings_context, unique_email  # noqa: E402

from billing.models import BillingPlan, BillingUsage  # noqa: E402
import database  # noqa: E402
from main import (  # noqa: E402
    AuthRequest,
    DebateCreate,
    DebateUpdate,
    TeamCreate,
    TeamMemberCreate,
    add_team_member,
    admin_logs,
    admin_ops_summary,
    create_debate,
    create_team,
    export_debate_report,
    export_scores_csv,
    get_debate,
    get_debate_events,
    get_leaderboard,
    get_model_leaderboard_stats,
    healthz,
    list_debates,
    register_user,
    start_debate_run,
    update_debate,
)
from models import AuditLog, Debate, PairwiseVote, RatingPersona, Score, UsageCounter, UsageQuota, User  # noqa: E402
import orchestrator as orchestrator_module  # noqa: E402
import debate_dispatch as debate_dispatch_module  # noqa: E402
from orchestrator import run_debate  # noqa: E402
from ratings import update_ratings_for_debate, wilson_interval  # noqa: E402
from schemas import default_debate_config, default_panel_config  # noqa: E402
from sse_backend import get_sse_backend, reset_sse_backend_for_tests  # noqa: E402
from parliament.provider_health import clear_all_health_states, record_call_result  # noqa: E402


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
    settings.reload()
    with pytest.raises(RuntimeError):
        importlib.reload(auth_module)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    settings.reload()
    importlib.reload(auth_module)


def dummy_request(path: str = "/debates") -> Request:
    host = f"testclient-{uuid.uuid4().hex}"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": (host, 0),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_health_endpoint_direct():
    result = asyncio.run(healthz())
    assert result["status"] == "ok"


def test_run_debate_emits_final_events():
    debate_id = "pytest-debate"
    with Session(database.engine) as session:
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
                panel_config=default_panel_config().model_dump(),
                engine_version="parliament-v1",
            )
        )
        session.commit()

    reset_sse_backend_for_tests()

    async def _collect_events():
        backend = get_sse_backend()
        channel_id = f"debate:{debate_id}"
        await backend.create_channel(channel_id)
        events: list[dict] = []

        async def _consume():
            async for event in backend.subscribe(channel_id):
                events.append(event)
                if event.get("type") in ("final", "error"):
                    break

        consumer = asyncio.create_task(_consume())
        await run_debate(debate_id, "Pytest prompt", channel_id, default_debate_config().model_dump())
        await consumer
        return events

    events = asyncio.run(_collect_events())

    seat_events = [event for event in events if event.get("type") == "seat_message"]
    with Session(database.engine) as session:
        stored = session.get(Debate, debate_id)
    if stored and stored.panel_config and settings.REQUIRE_REAL_LLM:
        assert seat_events, f"No seat_message events: {events}"
    final_events = [event for event in events if event.get("type") == "final"]
    assert final_events, f"No final event emitted: {events}"
    meta = final_events[-1]["meta"]
    assert "ranking" in meta
    assert "usage" in meta


def _register_user(email: str, password: str) -> User:
    body = AuthRequest(email=email, password=password)
    with Session(database.engine) as session:
        response = Response()
        try:
            asyncio.run(register_user(body, response, session))
        except HTTPException as exc:
            # Tests can call this helper repeatedly with the same email; reuse existing user.
            if exc.status_code == 400 and getattr(exc, "detail", "") == "email already registered":
                existing = session.exec(select(User).where(User.email == email.strip().lower())).first()
                if existing:
                    existing.role = "user"
                    existing.is_admin = False
                    session.add(existing)
                    session.commit()
            else:
                raise
        user = session.exec(select(User).where(User.email == email.strip().lower())).first()
        return user


def _create_debate_for_user(user: User, prompt: str) -> str:
    background_tasks = BackgroundTasks()
    request = dummy_request()
    body = DebateCreate(prompt=prompt)
    with Session(database.engine) as session:
        result = asyncio.run(
            create_debate(
                body,
                background_tasks,
                request,
                session,
                current_user=user,
            )
        )
    # Execute background tasks to mirror FastAPI behavior when routes are called directly
    if background_tasks.tasks:
        asyncio.run(background_tasks())
    debate_id = result["id"]
    with Session(database.engine) as session:
        debate = session.get(Debate, debate_id)
        if debate and not debate.user_id:
            debate.user_id = user.id
            session.add(debate)
            session.commit()
    return debate_id


def _create_team_for_user(owner: User, name: str = "Sepia Team") -> str:
    with Session(database.engine) as session:
        payload = TeamCreate(name=name)
        team_info = asyncio.run(create_team(payload, session=session, current_user=owner))
        return team_info["id"]


def _add_user_to_team(inviter: User, team_id: str, email: str, role: str = "viewer") -> None:
    with Session(database.engine) as session:
        payload = TeamMemberCreate(email=email, role=role)
        asyncio.run(add_team_member(team_id, payload, session=session, current_user=inviter))


def _assign_debate_to_team(actor: User, debate_id: str, team_id: str | None) -> None:
    with Session(database.engine) as session:
        payload = DebateUpdate(team_id=team_id)
        asyncio.run(update_debate(debate_id, payload, session=session, current_user=actor))


def test_export_scores_csv_endpoint():
    user = _register_user("csv@example.com", "secret123")
    debate_id = _create_debate_for_user(user, "CSV prompt")
    with Session(database.engine) as session:
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
    with Session(database.engine) as session:
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


def test_export_markdown_streams_content():
    user = _register_user("export-md@example.com", "secret123")
    debate_id = _create_debate_for_user(user, "Markdown export prompt")
    with Session(database.engine) as session:
        response = asyncio.run(
            export_debate_report(
                debate_id,
                session=session,
                current_user=user,
            )
        )
    body = response.body.decode()
    assert f"# Debate {debate_id}" in body
    assert "Markdown export prompt" in body


def test_billing_usage_increments_on_debate_create():
    user = _register_user("billing-check@example.com", "secret123")
    _create_debate_for_user(user, "Billing usage prompt")
    with Session(database.engine) as session:
        usage = session.exec(select(BillingUsage).where(BillingUsage.user_id == user.id)).first()
        assert usage is not None
        assert usage.debates_created >= 1


def test_get_debate_events_includes_pairwise_votes():
    debate_id = "pairwise-event-test"
    with Session(database.engine) as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
        session.add(
            Debate(
                id=debate_id,
                prompt="Pairwise prompt",
                status="completed",
                config=default_debate_config().model_dump(),
                panel_config=default_panel_config().model_dump(),
                engine_version="parliament-v1",
            )
        )
        session.add(
            PairwiseVote(
                debate_id=debate_id,
                candidate_a="Alpha",
                candidate_b="Beta",
                winner="A",
                judge_id="Judge-1",
            )
        )
        session.commit()

    with Session(database.engine) as session:
        payload = asyncio.run(get_debate_events(debate_id, session=session, current_user=None))

    pairwise_events = [item for item in payload["items"] if item["type"] == "pairwise"]
    assert pairwise_events, f"No pairwise events in {payload}"
    event = pairwise_events[0]
    assert event["candidate_a"] == "Alpha"
    assert event["candidate_b"] == "Beta"
    assert event["winner"] == "Alpha"
    assert event["loser"] == "Beta"
    assert event["judge_id"] == "Judge-1"


def test_user_scoped_debates_and_admin_access():
    owner = _register_user("owner@example.com", "ownerpass")
    reviewer = _register_user("stranger@example.com", "strangepass")
    debate_id = _create_debate_for_user(owner, "Owner prompt")

    with Session(database.engine) as session:
        owner_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=owner)
        )
        assert any(item.id == debate_id for item in owner_runs["items"])

    with Session(database.engine) as session:
        stranger_runs = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=reviewer)
        )
        assert all(item.id != debate_id for item in stranger_runs["items"])
        with pytest.raises(HTTPException):
            asyncio.run(get_debate(debate_id, session=session, current_user=reviewer))

    with Session(database.engine) as session:
        admin = session.get(User, reviewer.id)
        admin.role = "admin"
        session.add(admin)
        session.commit()

    with Session(database.engine) as session:
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
    with Session(database.engine) as session:
        payload = asyncio.run(
            list_debates(None, 1, 0, session=session, current_user=user)
        )
    assert "items" in payload and "total" in payload
    assert payload["total"] >= 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert isinstance(payload["has_more"], bool)


def test_list_debates_prompt_query_filters_results():
    user = _register_user("searcher@example.com", "search-pass")
    target = _create_debate_for_user(user, "Affordable housing now")
    _create_debate_for_user(user, "Totally different topic")
    with Session(database.engine) as session:
        payload = asyncio.run(
            list_debates(None, 20, 0, session=session, current_user=user, q="housing")
        )
    ids = [item.id for item in payload["items"]]
    assert target in ids


def test_rate_limit_blocks_after_threshold():
    if os.getenv("FASTAPI_TEST_MODE") == "1":
        pytest.skip("Rate limit enforcement skipped under FASTAPI_TEST_MODE for isolation")
    with settings_context(DEFAULT_MAX_RUNS_PER_HOUR="1"):
        user = _register_user("ratelimit@example.com", "securepass")
        _create_debate_for_user(user, "First allowed run")
        with pytest.raises(HTTPException) as exc_info:
            _create_debate_for_user(user, "Second run should fail")
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert detail["code"] == "rate_limit"
        with Session(database.engine) as session:
            logs = session.exec(
                select(AuditLog).where(AuditLog.action == "rate_limit_block", AuditLog.user_id == user.id)
            ).all()
            assert logs


def test_admin_logs_endpoint_lists_entries():
    owner = _register_user("auditor@example.com", "ownerpass")
    if os.getenv("FASTAPI_TEST_MODE") == "1":
        from sqlalchemy import delete
        with Session(database.engine) as session:
            session.exec(delete(UsageCounter))
            session.exec(delete(UsageQuota))
            session.commit()
    _create_debate_for_user(owner, "Audit trail run")
    with Session(database.engine) as session:
        admin = session.get(User, owner.id)
        admin.role = "admin"
        session.add(admin)
        session.commit()
    with Session(database.engine) as session:
        admin_user = session.get(User, owner.id)
        payload = asyncio.run(admin_logs(50, session, admin_user))
    assert payload["items"]
    assert any(entry["action"] == "debate_created" for entry in payload["items"])


def test_admin_ops_summary_reports_status():
    owner = _register_user("ops@example.com", "ownerpass")
    _create_debate_for_user(owner, "Ops trail run")
    clear_all_health_states()
    record_call_result("openai", "gpt-4o", success=False)
    record_call_result("openai", "gpt-4o", success=True)
    with Session(database.engine) as session:
        admin = session.get(User, owner.id)
        admin.role = "admin"
        session.add(admin)
        session.commit()
    with Session(database.engine) as session:
        admin_user = session.get(User, owner.id)
        payload = asyncio.run(admin_ops_summary(session=session, current_admin=admin_user))
    assert "debates_24h" in payload
    assert payload["rate_limit"]["backend"]
    assert payload["dispatch"]["mode"]
    assert "provider_health" in payload
    assert isinstance(payload["provider_health"], list)
    if payload["provider_health"]:
        entry = payload["provider_health"][0]
        assert {"provider", "model", "error_rate", "total_calls", "is_open", "last_opened"} <= set(entry.keys())


def test_wilson_interval_bounds():
    low, high = wilson_interval(8, 10)
    assert 0.4 < low < high < 1.0


def test_leaderboard_updates_after_score_entries(monkeypatch):
    user = _register_user(f"elo-{uuid.uuid4().hex[:8]}@example.com", "elo-pass")
    debate_id = _create_debate_for_user(user, "Leaderboard prompt")
    with Session(database.engine) as session:
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
    
    # Temporarily enable ratings without reloading settings (to avoid DB switch)
    monkeypatch.setattr(settings, "DISABLE_RATINGS", False)
    update_ratings_for_debate(debate_id)
        
    with Session(database.engine) as session:
        ratings = session.exec(select(RatingPersona).where(RatingPersona.persona == "Analyst")).all()
        assert ratings
        leaderboard = asyncio.run(get_leaderboard(Response(), None, 0, 10, session))
    assert any(entry["persona"] == "Analyst" for entry in leaderboard["items"])


def test_model_leaderboard_stats_counts_champions():
    persona_a = "StatsModelA"
    persona_b = "StatsModelB"
    with Session(database.engine) as session:
        for idx in range(4):
            debate_id = f"stats-leaderboard-{idx}"
            existing = session.get(Debate, debate_id)
            if existing:
                session.delete(existing)
            session.add(
                Debate(
                    id=debate_id,
                    prompt=f"Leaderboard prompt {idx}",
                    status="completed",
                    config=default_debate_config().model_dump(),
                )
            )
            if idx < 3:
                session.add(
                    Score(
                        debate_id=debate_id,
                        persona=persona_a,
                        judge=f"Judge-A-{idx}",
                        score=9.0,
                        rationale="A strong",
                    )
                )
                session.add(
                    Score(
                        debate_id=debate_id,
                        persona=persona_b,
                        judge=f"Judge-B-{idx}",
                        score=6.0,
                        rationale="B weak",
                    )
                )
            else:
                session.add(
                    Score(
                        debate_id=debate_id,
                        persona=persona_a,
                        judge=f"Judge-A-{idx}",
                        score=6.0,
                        rationale="A weak",
                    )
                )
                session.add(
                    Score(
                        debate_id=debate_id,
                        persona=persona_b,
                        judge=f"Judge-B-{idx}",
                        score=9.5,
                        rationale="B strong",
                    )
                )
        session.commit()

    with Session(database.engine) as session:
        summaries = asyncio.run(get_model_leaderboard_stats(session=session))

    entry_a = next(summary for summary in summaries if summary.model == persona_a)
    entry_b = next(summary for summary in summaries if summary.model == persona_b)
    assert entry_a.wins == 3
    assert entry_b.wins == 1
    assert entry_a.win_rate > entry_b.win_rate


def test_manual_start_requires_flag():
    from exceptions import ValidationError
    with settings_context(DISABLE_AUTORUN="0"):
        user = _register_user("manual-guard@example.com", "manualpass")
        debate_id = _create_debate_for_user(user, "Manual guard prompt")
        with Session(database.engine) as session:
            background_tasks = BackgroundTasks()
            with pytest.raises(ValidationError):
                asyncio.run(
                    start_debate_run(
                        debate_id,
                        background_tasks,
                        session=session,
                        current_user=user,
                    )
                )


def test_manual_start_succeeds_when_disabled():
    with settings_context(DISABLE_AUTORUN="1"):
        user = _register_user("manual-ok@example.com", "manualpass")
        debate_id = _create_debate_for_user(user, "Manual start run prompt")
        with Session(database.engine) as session:
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


def test_debate_creation_dispatches_celery_task(monkeypatch):
    with settings_context(
        DEBATE_DISPATCH_MODE="celery",
        DISABLE_AUTORUN="0",
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="memory://",
    ):
        class DummyTask:
            def __init__(self):
                self.debate_id = None

            def delay(self, debate_id: str):
                self.debate_id = debate_id

        dummy = DummyTask()
        monkeypatch.setattr(debate_dispatch_module, "run_debate_task", dummy, raising=False)

        user = _register_user("celery-dispatch@example.com", "celerypass")
        debate_id = _create_debate_for_user(user, "Celery dispatch prompt")
        assert dummy.debate_id == debate_id


def test_sweep_stale_channels_removes_old_entries():
    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    backend._ttl_seconds = 0.01  # Patch the instance directly
    channel_id = "stale-channel"
    asyncio.run(backend.create_channel(channel_id))
    time.sleep(0.02)
    asyncio.run(backend.cleanup())
    assert not backend._channels or not backend._channels.get(channel_id)


def test_admin_ops_summary_reports_status():
    admin = _register_user("admin-ops@example.com", "secret123")
    
    with Session(database.engine) as session:
        # Mock provider health
        record_call_result("openai", "gpt-4", success=True)
        record_call_result("anthropic", "claude-2", success=False)
        
        # Call endpoint
        result = asyncio.run(admin_ops_summary(session=session, current_admin=admin))
        
        assert "provider_health" in result
        health = result["provider_health"]
        assert len(health) >= 2
        
        openai = next(h for h in health if h["provider"] == "openai")
        assert openai["total_calls"] >= 1
        
        anthropic = next(h for h in health if h["provider"] == "anthropic")
        assert anthropic["error_calls"] >= 1
        
        # Clean up
        clear_all_health_states()
