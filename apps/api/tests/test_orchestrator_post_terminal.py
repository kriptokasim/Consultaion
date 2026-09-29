"""Side effects after a committed terminal state must not fail the run.

Once ``complete_debate()`` commits, a publish, email or bookkeeping error used
to fall into the generic failure handler: it marked the continuation failed,
sent a false "execution failed" alert, attempted a fenced running->failed
update that the committed status rejects, and re-raised before hosted credit
was settled or the viewer received a terminal event.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agents import UsageAccumulator
from models import Debate
from sqlmodel import Session

from tests.utils import ensure_user


@pytest.fixture
def real_pipeline(monkeypatch):
    import config as config_module

    monkeypatch.setenv("FAST_DEBATE", "0")
    config_module.settings.reload()
    yield
    monkeypatch.delenv("FAST_DEBATE", raising=False)
    config_module.settings.reload()


def _seed(db_session: Session, debate_id: str, mode: str) -> None:
    ensure_user(db_session, "post-terminal-user")
    db_session.add(
        Debate(
            id=debate_id,
            prompt="post terminal",
            status="queued",
            mode=mode,
            user_id="post-terminal-user",
        )
    )
    db_session.commit()


class _RecordingBackend:
    """SSE backend double that records events and fails on chosen types."""

    def __init__(self, fail_types: set[str]):
        self.fail_types = fail_types
        self.events: list[dict] = []

    async def publish(self, channel_id, event):
        if event.get("type") in self.fail_types:
            raise RuntimeError(f"publish failed for {event.get('type')}")
        self.events.append(event)


def _result(status: str, answer: str = "answer"):
    return SimpleNamespace(
        final_answer=answer,
        final_meta={"error": "boom"} if status == "failed" else {},
        status=status,
        usage_tracker=UsageAccumulator(),
        error_reason="boom" if status == "failed" else None,
    )


@pytest.mark.anyio
async def test_terminal_publish_failure_after_commit_keeps_run_completed(
    db_session, monkeypatch, real_pipeline
):
    import orchestrator
    from compare import engine as compare_engine

    debate_id = "post-terminal-publish"
    _seed(db_session, debate_id, "compare")

    backend = _RecordingBackend(fail_types={"final"})
    monkeypatch.setattr(orchestrator, "get_sse_backend", lambda: backend)
    monkeypatch.setattr(
        compare_engine, "run_compare_debate", AsyncMock(return_value=_result("completed"))
    )
    slack = AsyncMock()
    monkeypatch.setattr(orchestrator, "send_slack_alert", slack)
    settle = AsyncMock()
    monkeypatch.setattr(orchestrator, "_settle_terminal_hosted_credit", settle)

    # Must not raise: the run finished; only the notification failed.
    await orchestrator.run_debate(debate_id, "post terminal", f"debate:{debate_id}", {})

    db_session.expire_all()
    assert db_session.get(Debate, debate_id).status == "completed"
    slack.assert_not_awaited()
    settle.assert_awaited_once_with(debate_id, None)


@pytest.mark.anyio
async def test_error_after_success_commit_skips_failure_handler(
    db_session, monkeypatch, real_pipeline
):
    """Even an unisolated error after the commit must not be reported as failure."""
    import orchestrator
    from compare import engine as compare_engine

    debate_id = "post-terminal-late-error"
    _seed(db_session, debate_id, "compare")

    backend = _RecordingBackend(fail_types=set())
    monkeypatch.setattr(orchestrator, "get_sse_backend", lambda: backend)
    monkeypatch.setattr(
        compare_engine, "run_compare_debate", AsyncMock(return_value=_result("completed"))
    )

    calls = {"n": 0}

    async def _continuation(*args, **kwargs):
        calls["n"] += 1
        if args[1] == "completed":
            raise RuntimeError("late bookkeeping failure")

    monkeypatch.setattr(orchestrator, "_update_continuation_status", _continuation)
    slack = AsyncMock()
    monkeypatch.setattr(orchestrator, "send_slack_alert", slack)
    settle = AsyncMock()
    monkeypatch.setattr(orchestrator, "_settle_terminal_hosted_credit", settle)

    await orchestrator.run_debate(debate_id, "post terminal", f"debate:{debate_id}", {})

    db_session.expire_all()
    assert db_session.get(Debate, debate_id).status == "completed"
    slack.assert_not_awaited()
    settle.assert_awaited_once_with(debate_id, None)
    assert not any(e.get("type") == "debate_failed" for e in backend.events)


@pytest.mark.anyio
async def test_failed_compare_run_emits_debate_failed_not_final(
    db_session, monkeypatch, real_pipeline
):
    import orchestrator
    from compare import engine as compare_engine

    debate_id = "post-terminal-compare-failed"
    _seed(db_session, debate_id, "compare")

    backend = _RecordingBackend(fail_types=set())
    monkeypatch.setattr(orchestrator, "get_sse_backend", lambda: backend)
    monkeypatch.setattr(
        compare_engine, "run_compare_debate", AsyncMock(return_value=_result("failed", ""))
    )
    monkeypatch.setattr(orchestrator, "_settle_terminal_hosted_credit", AsyncMock())

    await orchestrator.run_debate(debate_id, "post terminal", f"debate:{debate_id}", {})

    types = [e.get("type") for e in backend.events]
    assert "final" not in types
    failed = [e for e in backend.events if e.get("type") == "debate_failed"]
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert failed[0]["reason"] == "boom"


@pytest.mark.anyio
async def test_successful_compare_run_final_event_carries_status(
    db_session, monkeypatch, real_pipeline
):
    import orchestrator
    from compare import engine as compare_engine

    debate_id = "post-terminal-compare-ok"
    _seed(db_session, debate_id, "compare")

    backend = _RecordingBackend(fail_types=set())
    monkeypatch.setattr(orchestrator, "get_sse_backend", lambda: backend)
    monkeypatch.setattr(
        compare_engine, "run_compare_debate", AsyncMock(return_value=_result("completed"))
    )
    monkeypatch.setattr(orchestrator, "_settle_terminal_hosted_credit", AsyncMock())

    await orchestrator.run_debate(debate_id, "post terminal", f"debate:{debate_id}", {})

    finals = [e for e in backend.events if e.get("type") == "final"]
    assert len(finals) == 1
    assert finals[0]["status"] == "completed"
    assert finals[0]["payload"]["content"] == "answer"
    # The start notice is published only after the lease is owned.
    assert backend.events[0]["type"] == "notice"
