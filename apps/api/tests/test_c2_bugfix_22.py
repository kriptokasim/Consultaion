from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _Stream:
    def __init__(self, chunks):
        self._chunks = iter(chunks)
        self._done = object()

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = next(self._chunks, self._done)
        if value is self._done:
            raise StopAsyncIteration
        if isinstance(value, BaseException):
            raise value
        return value


def _chunk(text: str = "", *, usage=None, cost: float = 0.0):
    choices = []
    if text:
        choices = [SimpleNamespace(delta=SimpleNamespace(content=text))]
    return SimpleNamespace(
        choices=choices,
        usage=usage,
        _hidden_params={"response_cost": cost},
    )


@pytest.mark.anyio
async def test_direct_stream_preserves_provider_usage_and_cost(monkeypatch):
    from model_gateway import adapters

    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Stream(
            [
                _chunk("Visible "),
                _chunk("answer"),
                _chunk(
                    usage={
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                    },
                    cost=0.0123,
                ),
            ]
        )

    monkeypatch.setattr(adapters, "acompletion", fake_acompletion)
    result = await adapters.DirectProviderAdapter().stream_llm(
        messages=[{"role": "user", "content": "Question"}],
        model_id="openai_fast",
        temperature=0.1,
        max_tokens=100,
        gateway_policy="direct",
        model_pool="standard",
        routing_policy="direct",
        on_delta=AsyncMock(),
    )

    assert captured["stream_options"] == {"include_usage": True}
    assert result.content == "Visible answer"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert result.total_tokens == 18
    assert result.cost_usd == pytest.approx(0.0123)


@pytest.mark.anyio
async def test_openrouter_stream_preserves_provider_usage_and_cost(monkeypatch):
    from model_gateway import adapters

    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Stream(
            [
                _chunk("Answer"),
                _chunk(
                    usage={
                        "prompt_tokens": 13,
                        "completion_tokens": 5,
                        "total_tokens": 18,
                    },
                    cost=0.008,
                ),
            ]
        )

    monkeypatch.setattr(adapters, "acompletion", fake_acompletion)
    result = await adapters.OpenRouterAdapter().stream_llm(
        messages=[{"role": "user", "content": "Question"}],
        model_id="openrouter_fallback",
        temperature=0.1,
        max_tokens=100,
        gateway_policy="openrouter",
        model_pool="standard",
        routing_policy="openrouter",
        on_delta=AsyncMock(),
    )

    assert captured["stream_options"] == {"include_usage": True}
    assert result.content == "Answer"
    assert result.prompt_tokens == 13
    assert result.completion_tokens == 5
    assert result.total_tokens == 18
    assert result.cost_usd == pytest.approx(0.008)


@pytest.mark.anyio
async def test_interrupted_stream_keeps_partial_usage_estimate(monkeypatch):
    from model_gateway import adapters

    async def fake_acompletion(**_kwargs):
        return _Stream([_chunk("Partial"), asyncio.TimeoutError()])

    monkeypatch.setattr(adapters, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        adapters,
        "_estimate_stream_usage",
        lambda **_kwargs: (9, 3, 12, 0.004),
    )
    result = await adapters.DirectProviderAdapter().stream_llm(
        messages=[{"role": "user", "content": "Question"}],
        model_id="openai_fast",
        temperature=0.1,
        max_tokens=100,
        gateway_policy="direct",
        model_pool="standard",
        routing_policy="direct",
        on_delta=AsyncMock(),
    )

    assert result.success is False
    assert result.content == "Partial"
    assert result.total_tokens == 12
    assert result.cost_usd == pytest.approx(0.004)


def test_report_normalization_failure_is_nonfatal(monkeypatch):
    from arena.engine import _build_synthesis_report_nonfatal
    from reporting import report_builder

    monkeypatch.setattr(
        report_builder,
        "build_report_from_synthesis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("Confidence 999%")),
    )
    assert _build_synthesis_report_nonfatal(
        prompt="Question",
        content="Already streamed and billable final",
        model_responses=[],
        debate_id="debate-1",
        synthesis_id="synth-1",
    ) is None


@pytest.mark.anyio
async def test_canonical_terminal_commit_precedes_record_and_settle(monkeypatch):
    from models import DebateAttempt
    from orchestration.state import DebateStateManager

    events: list[str] = []
    debate = SimpleNamespace(final_content=None, final_meta=None, status="running", updated_at=None)
    attempt = SimpleNamespace(status="running", tokens_used=0, completed_at=None)

    class Session:
        async def get(self, model, _identifier):
            return attempt if model is DebateAttempt else debate

        def add(self, _value):
            return None

        async def commit(self):
            events.append("terminal_commit")

    @asynccontextmanager
    async def fake_async_scope():
        yield Session()

    @contextmanager
    def fake_sync_scope():
        yield SimpleNamespace()

    monkeypatch.setattr("orchestration.state.async_session_scope", fake_async_scope)
    monkeypatch.setattr("database.session_scope", fake_sync_scope)
    monkeypatch.setattr("json_contracts.safe_validate_final_meta", lambda _meta: None)
    monkeypatch.setattr(
        "services.usage_ledger.record_token_usage",
        lambda *_args, **_kwargs: events.append("record") or SimpleNamespace(status="reserved"),
    )
    monkeypatch.setattr(
        "services.usage_ledger.settle_token_usage",
        lambda *_args, **_kwargs: events.append("settle"),
    )
    manager = DebateStateManager("debate-1", user_id="user-1", attempt_id="attempt-1")
    monkeypatch.setattr(manager, "_update_checkpoint_in_session", AsyncMock())

    await manager.complete_debate("Final", {}, "completed", tokens_total=42)

    assert events == ["terminal_commit", "record", "settle"]


@pytest.mark.anyio
async def test_parliament_budget_boundary_applies_without_router_import(monkeypatch):
    import parliament_budget_guard as guard

    guard._states.clear()
    guard._states["debate-1"] = guard._BudgetState(max_tokens=1, max_cost_usd=None)
    usage = SimpleNamespace(total_tokens=1, cost_usd=0.0)
    monkeypatch.setattr(guard, "_call_llm_for_role", AsyncMock(return_value=("ok", usage)))

    assert await guard.call_llm_for_role_budgeted([], debate_id="debate-1") == ("ok", usage)
    with pytest.raises(guard.ParliamentBudgetExceeded, match="token_budget_exceeded"):
        await guard.call_llm_for_role_budgeted([], debate_id="debate-1")
