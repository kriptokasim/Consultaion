import threading

import pytest
from integrations import events as events_module


@pytest.fixture(autouse=True)
def _restore_webhook_url():
    original = events_module.settings.N8N_WEBHOOK_URL
    yield
    events_module.settings.N8N_WEBHOOK_URL = original


def test_emit_event_runs_in_background(monkeypatch):
    called = threading.Event()

    async def fake_send(url, event, payload):
        called.set()

    events_module.settings.N8N_WEBHOOK_URL = "http://example.com/webhook"
    monkeypatch.setattr(events_module, "_send_event_async", fake_send)
    events_module.emit_event("test", {"foo": "bar"})
    assert called.wait(timeout=1)


def test_emit_event_swallows_errors(monkeypatch):
    async def boom(url, event, payload):
        raise RuntimeError("boom")

    events_module.settings.N8N_WEBHOOK_URL = "http://example.com/webhook"
    monkeypatch.setattr(events_module, "_send_event_async", boom)
    events_module.emit_event("test", {"foo": "bar"})
    # Should not raise even if the background task fails
