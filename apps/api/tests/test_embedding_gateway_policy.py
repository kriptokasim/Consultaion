"""Embeddings are spend, and must obey the same policy as every other LLM call.

reporting/claim_similarity.py calls litellm.aembedding() directly rather than
going through model_gateway.route_llm_call(), so none of the gateway's controls
reached it: no FREE_ONLY_MODE gate, no kill switch, no circuit breaker, no
budget. Production showed the consequence -- 29 identical 429s
("You have no credits remaining") in eight seconds against a dead OpenAI account,
on a deployment that had FREE_ONLY_MODE switched on. The synthesis still
completed, because the caller falls back to string similarity, which is exactly
why it went unnoticed.

These tests pin the policy, not the transport: the call must be skipped when
policy forbids it, and must stop retrying a dead upstream.
"""
from __future__ import annotations

import pytest

import reporting.claim_similarity as cs

pytestmark = [pytest.mark.anyio, pytest.mark.timeout(10)]


@pytest.fixture(autouse=True)
def _reset_circuit():
    cs._note_embedding_success()
    yield
    cs._note_embedding_success()


@pytest.fixture
def paid_mode(monkeypatch):
    monkeypatch.setattr("config.settings.USE_MOCK", False)
    monkeypatch.setattr("config.settings.FREE_ONLY_MODE", False)
    monkeypatch.setattr("config.settings.LLM_KILL_SWITCH_ENABLED", False)
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "direct")


def _spy(monkeypatch, result=None, error=None):
    calls = []

    async def fake_aembedding(**kwargs):
        calls.append(kwargs)
        if error:
            raise error
        return result or {"data": [{"embedding": [0.1, 0.2]}]}

    monkeypatch.setattr(cs, "aembedding", fake_aembedding)
    return calls


async def test_free_only_mode_skips_a_paid_embedding_model(monkeypatch, paid_mode):
    """The production case: free-only on, paid embedding model, no credit."""
    monkeypatch.setattr("config.settings.FREE_ONLY_MODE", True)
    monkeypatch.setattr("config.settings.EMBEDDING_MODEL", "openai/text-embedding-3-small")
    calls = _spy(monkeypatch)

    result = await cs.get_claim_embeddings(["a claim"], "debate-1")

    assert result == [], "caller must fall back to string similarity"
    assert calls == [], "a paid embedding must not be called in FREE_ONLY_MODE"


async def test_kill_switch_skips_the_call(monkeypatch, paid_mode):
    monkeypatch.setattr("config.settings.LLM_KILL_SWITCH_ENABLED", True)
    calls = _spy(monkeypatch)

    assert await cs.get_claim_embeddings(["a claim"]) == []
    assert calls == []


async def test_normal_mode_still_embeds(monkeypatch, paid_mode):
    """The guard must not disable the feature it is protecting."""
    calls = _spy(monkeypatch)

    result = await cs.get_claim_embeddings(["a claim"])

    assert result == [[0.1, 0.2]]
    assert len(calls) == 1


async def test_repeated_failures_open_a_cooldown(monkeypatch, paid_mode):
    """Stops the 29-calls-in-8-seconds storm against a dead upstream."""
    calls = _spy(monkeypatch, error=RuntimeError("429 insufficient_quota"))

    for _ in range(cs._EMBED_FAILURE_THRESHOLD):
        assert await cs.get_claim_embeddings(["a claim"]) == []
    assert len(calls) == cs._EMBED_FAILURE_THRESHOLD

    # Further attempts are refused locally rather than sent upstream.
    for _ in range(5):
        assert await cs.get_claim_embeddings(["a claim"]) == []
    assert len(calls) == cs._EMBED_FAILURE_THRESHOLD, "cooldown did not stop the retries"


async def test_a_success_closes_the_cooldown(monkeypatch, paid_mode):
    calls = _spy(monkeypatch, error=RuntimeError("boom"))
    for _ in range(cs._EMBED_FAILURE_THRESHOLD):
        await cs.get_claim_embeddings(["a claim"])
    assert cs._embedding_cooldown_active()

    cs._note_embedding_success()
    assert not cs._embedding_cooldown_active()

    _spy(monkeypatch)
    assert await cs.get_claim_embeddings(["a claim"]) == [[0.1, 0.2]]


async def test_proxy_backend_routes_embeddings_through_the_proxy(monkeypatch, paid_mode):
    """Otherwise the proxy's spend ceiling measures a subset of real spend."""
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "proxy")
    monkeypatch.setattr("config.settings.LITELLM_PROXY_URL", "http://litellm:4000/")
    monkeypatch.setattr("config.settings.LITELLM_PROXY_API_KEY", "sk-virtual")
    calls = _spy(monkeypatch)

    await cs.get_claim_embeddings(["a claim"])

    assert calls[0]["api_base"] == "http://litellm:4000"
    assert calls[0]["api_key"] == "sk-virtual"


async def test_direct_backend_passes_no_proxy_kwargs(monkeypatch, paid_mode):
    calls = _spy(monkeypatch)

    await cs.get_claim_embeddings(["a claim"])

    assert "api_base" not in calls[0]
    assert "api_key" not in calls[0]
