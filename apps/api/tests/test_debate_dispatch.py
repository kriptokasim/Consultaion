import pytest

import debate_dispatch
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

        def delay(self, debate_id: str):
            self.debate_id = debate_id

    dummy = DummyTask()
    monkeypatch.setattr(debate_dispatch, "run_debate_task", dummy, raising=False)
    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery", raising=False)
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "memory://", raising=False)
    monkeypatch.setattr(settings, "CELERY_RESULT_BACKEND", "memory://", raising=False)

    await debate_dispatch.dispatch_debate_run(
        "deb-2",
        "Prompt",
        "debate:deb-2",
        {"agents": []},
        None,
    )
    assert dummy.debate_id == "deb-2"
