import debate_dispatch
import pytest
from config import settings


@pytest.mark.anyio
async def test_dispatch_inline_invokes_local_engine(monkeypatch):
    called = {}

    async def fake_run(*args, **kwargs):
        called["ran"] = True

    monkeypatch.setattr(debate_dispatch, "run_debate", fake_run, raising=False)
    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "inline", raising=False)

    await debate_dispatch.dispatch_debate_run(
        "deb-1",
        "Prompt",
        "debate:deb-1",
        {"agents": []},
        None,
    )

    assert called.get("ran") is True


@pytest.mark.anyio
async def test_dispatch_celery_queues_task(monkeypatch):
    class DummyTask:
        def __init__(self):
            self.debate_id = None
            self.kwargs = {}

        def apply_async(self, args=None, queue=None):
            self.debate_id = args[0] if args else None
            self.kwargs = {"args": args, "queue": queue}

    dummy = DummyTask()
    monkeypatch.setattr(debate_dispatch, "run_debate_task", dummy, raising=False)
    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery", raising=False)
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "memory://", raising=False)
    monkeypatch.setattr(settings, "CELERY_RESULT_BACKEND", "memory://", raising=False)
    monkeypatch.setattr(settings, "DEBATE_FAST_QUEUE_NAME", "fast-q", raising=False)
    monkeypatch.setattr(settings, "DEBATE_DEFAULT_QUEUE", "default-q", raising=False)

    await debate_dispatch.dispatch_debate_run(
        "deb-2",
        "Prompt",
        "debate:deb-2",
        {"agents": [], "mode": "fast"},
        None,
    )
    assert dummy.debate_id == "deb-2"
    assert dummy.kwargs["queue"] == "fast-q"


def test_choose_queue_for_debate_uses_mode(monkeypatch):
    monkeypatch.setattr(settings, "DEBATE_FAST_QUEUE_NAME", "fast-line", raising=False)
    monkeypatch.setattr(settings, "DEBATE_DEEP_QUEUE_NAME", "deep-line", raising=False)
    monkeypatch.setattr(settings, "DEBATE_DEFAULT_QUEUE", "default-line", raising=False)
    assert debate_dispatch.choose_queue_for_debate({"mode": "fast"}, settings) == "fast-line"
    assert debate_dispatch.choose_queue_for_debate({"mode": "deep"}, settings) == "deep-line"


def test_choose_queue_for_debate_defaults(monkeypatch):
    monkeypatch.setattr(settings, "DEBATE_DEFAULT_QUEUE", "fallback-line", raising=False)
    assert debate_dispatch.choose_queue_for_debate({}, settings) == "fallback-line"
