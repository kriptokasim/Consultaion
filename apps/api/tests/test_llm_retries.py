
import agents
import pytest
from agents import UsageCall, call_llm_with_retry
from config import settings
from llm_errors import TransientLLMError


class _StubCall:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if outcome == "fail":
            raise TransientLLMError("transient")
        return outcome, UsageCall(provider="stub", model="stub-model")


@pytest.mark.anyio("asyncio")
async def test_llm_retry_disabled(monkeypatch):
    original = settings.LLM_RETRY_ENABLED
    settings.LLM_RETRY_ENABLED = False
    stub = _StubCall(["ok"])
    monkeypatch.setattr(agents, "_raw_llm_call", stub)
    try:
        payload = await call_llm_with_retry([], role="tester")
        assert payload[0] == "ok"
        assert stub.calls == 1
    finally:
        settings.LLM_RETRY_ENABLED = original


@pytest.mark.anyio("asyncio")
async def test_llm_retry_succeeds_after_transient(monkeypatch):
    original = (settings.LLM_RETRY_ENABLED, settings.LLM_RETRY_MAX_ATTEMPTS, settings.LLM_RETRY_INITIAL_DELAY_SECONDS)
    settings.LLM_RETRY_ENABLED = True
    settings.LLM_RETRY_MAX_ATTEMPTS = 3
    settings.LLM_RETRY_INITIAL_DELAY_SECONDS = 0
    stub = _StubCall(["fail", "ok"])
    monkeypatch.setattr(agents, "_raw_llm_call", stub)
    try:
        payload = await call_llm_with_retry([], role="tester")
        assert payload[0] == "ok"
        assert stub.calls == 2
    finally:
        settings.LLM_RETRY_ENABLED, settings.LLM_RETRY_MAX_ATTEMPTS, settings.LLM_RETRY_INITIAL_DELAY_SECONDS = original


@pytest.mark.anyio("asyncio")
async def test_llm_retry_raises_after_max_attempts(monkeypatch):
    original = (settings.LLM_RETRY_ENABLED, settings.LLM_RETRY_MAX_ATTEMPTS, settings.LLM_RETRY_INITIAL_DELAY_SECONDS)
    settings.LLM_RETRY_ENABLED = True
    settings.LLM_RETRY_MAX_ATTEMPTS = 2
    settings.LLM_RETRY_INITIAL_DELAY_SECONDS = 0
    stub = _StubCall(["fail", "fail"])
    monkeypatch.setattr(agents, "_raw_llm_call", stub)
    try:
        with pytest.raises(TransientLLMError):
            await call_llm_with_retry([], role="tester")
        assert stub.calls == 2
    finally:
        settings.LLM_RETRY_ENABLED, settings.LLM_RETRY_MAX_ATTEMPTS, settings.LLM_RETRY_INITIAL_DELAY_SECONDS = original
