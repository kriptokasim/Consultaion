"""Arena engine regressions from the run-flow audit."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.test_arena_failure_resilience import (
    _ARENA_MODELS,
    _bypass_checkpoint,
    _FakeUsage,
    _mock_session_scope,
)


def _settings(mock_settings, *, streaming: bool, min_required: int = 1, slots: int = 6):
    mock_settings.FAST_DEBATE = False
    mock_settings.STREAMING_RESPONSES_ENABLED = streaming
    mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
    mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
    mock_settings.ARENA_MAX_TOKENS = 1200
    mock_settings.ARENA_DELTA_FLUSH_MS = 0
    mock_settings.STAGED_DECISION_PIPELINE = False
    mock_settings.ARENA_PROGRESSIVE_SYNTHESIS_ENABLED = False
    mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = min_required
    mock_settings.LLM_MAX_CONCURRENT_CALLS_PER_RUN = slots
    mock_settings.ARENA_SYNTHESIS_MODEL = None


def _report():
    report = MagicMock()
    report.executive_summary = "Verdict"
    report.title = "Report"
    report.divergence_breakdown = []
    report.model_dump.return_value = {}
    return report


@pytest.mark.anyio
async def test_quorum_shortfall_is_not_reported_as_all_models_failed():
    from arena.engine import run_arena

    async def only_a(*args, **kwargs):
        if "Model A" in kwargs.get("role", ""):
            return "Answer A", _FakeUsage()
        raise RuntimeError("provider down")

    with (
        patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS),
        patch("arena.engine.call_llm_for_role", side_effect=only_a),
        patch("arena.engine.get_sse_backend", return_value=AsyncMock()),
        patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope),
        patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint),
        patch("config.settings") as mock_settings,
    ):
        _settings(mock_settings, streaming=False, min_required=2)
        result = await run_arena("quorum-shortfall")

    assert result.status == "failed"
    assert result.error_reason == "insufficient_responses"
    assert result.final_meta["successful_count"] == 1
    assert result.final_meta["total_count"] == 3
    assert result.final_meta["min_required"] == 2
    assert "Only 1 of 3" in result.final_answer


@pytest.mark.anyio
async def test_stream_failure_after_output_does_not_pay_for_a_second_call():
    from arena.engine import run_arena

    async def stream_then_fail(*, on_delta=None, **kwargs):
        from model_gateway.types import ModelDelta

        await on_delta(ModelDelta(text="partial answer ", sequence=1, accumulated_chars=15))
        return SimpleNamespace(
            success=False,
            content="partial answer ",
            error_message="connection reset",
            error_code="model_timeout",
        )

    fallback = AsyncMock(return_value=("full answer", _FakeUsage()))
    with (
        patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS[:1]),
        patch("model_gateway.route_llm_stream", side_effect=stream_then_fail),
        patch("arena.engine.call_llm_for_role", fallback),
        patch("arena.engine.get_sse_backend", return_value=AsyncMock()),
        patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope),
        patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint),
        patch("config.settings") as mock_settings,
    ):
        _settings(mock_settings, streaming=True)
        result = await run_arena("stream-interrupted")

    fallback.assert_not_awaited()
    [response] = result.model_responses
    assert response.success is False
    assert response.error_code == "stream_interrupted"


@pytest.mark.anyio
async def test_stream_failure_before_output_still_falls_back_once():
    from arena.engine import run_arena

    async def fail_immediately(*, on_delta=None, **kwargs):
        return SimpleNamespace(
            success=False, content="", error_message="connect failed", error_code="model_timeout"
        )

    fallback = AsyncMock(return_value=("full answer", _FakeUsage()))
    with (
        patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS[:1]),
        patch("model_gateway.route_llm_stream", side_effect=fail_immediately),
        patch("arena.engine.call_llm_for_role", fallback),
        patch("arena.engine.get_sse_backend", return_value=AsyncMock()),
        patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope),
        patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint),
        patch("reporting.synthesizer.generate_decision_report", return_value=_report()),
        patch("config.settings") as mock_settings,
    ):
        _settings(mock_settings, streaming=True)
        result = await run_arena("stream-failed-early")

    fallback.assert_awaited_once()
    assert result.model_responses[0].success is True


@pytest.mark.anyio
async def test_every_model_is_marked_queued_before_any_call_starts():
    from arena.engine import run_arena

    backend = AsyncMock()

    async def answer(*args, **kwargs):
        return "Answer", _FakeUsage()

    with (
        patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS),
        patch("arena.engine.call_llm_for_role", side_effect=answer),
        patch("arena.engine.get_sse_backend", return_value=backend),
        patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope),
        patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint),
        patch("reporting.synthesizer.generate_decision_report", return_value=_report()),
        patch("config.settings") as mock_settings,
    ):
        # One slot: models two and three wait behind the first call.
        _settings(mock_settings, streaming=False, slots=1)
        await run_arena("queued-first")

    lifecycle = [
        call.args[1]
        for call in backend.publish.await_args_list
        if call.args[1].get("type", "").startswith("model_response_")
    ]
    queued = [e["model_id"] for e in lifecycle if e["type"] == "model_response_queued"]
    first_connecting = next(
        i for i, e in enumerate(lifecycle) if e["type"] == "model_response_connecting"
    )
    assert queued == ["model-a", "model-b", "model-c"]
    assert first_connecting == 3


@pytest.mark.anyio
async def test_synthesize_verdict_does_not_absorb_ownership_loss():
    from agents import UsageAccumulator
    from arena.engine import ArenaModelResponse, _synthesize_verdict
    from orchestration.execution_lease import ExecutionSupersededError

    responses = [
        ArenaModelResponse(model_id="m", display_name="M", provider="openai", content="x", success=True)
    ]
    with patch(
        "reporting.synthesizer.generate_decision_report",
        AsyncMock(side_effect=ExecutionSupersededError("taken over")),
    ):
        with pytest.raises(ExecutionSupersededError):
            await _synthesize_verdict(
                debate_id="d",
                prompt="p",
                model_responses=responses,
                usage=UsageAccumulator(),
            )


def _info(model_id: str, quality: str):
    return SimpleNamespace(id=model_id, quality_tier=quality)


def _resp(model_id: str, success: bool = True):
    return SimpleNamespace(model_id=model_id, success=success)


def test_synthesis_model_prefers_configured_then_best_panel_then_routed():
    from arena import engine

    registry = {
        "free": _info("free", "baseline"),
        "mid": _info("mid", "advanced"),
        "top": _info("top", "flagship"),
        "chair": _info("chair", "flagship"),
    }
    enabled = [SimpleNamespace(id=k) for k in ("free", "mid", "top", "chair")]
    with (
        patch.object(engine, "resolve_model_info", side_effect=registry.get),
        patch("parliament.model_registry.list_enabled_models", return_value=enabled),
        patch("config.settings") as mock_settings,
    ):
        mock_settings.ARENA_SYNTHESIS_MODEL = None
        responses = [_resp("free"), _resp("top", success=False), _resp("mid")]
        # The failed flagship is skipped; the best model that answered wins.
        assert engine._choose_synthesis_model(responses, "free") == "mid"
        assert engine._choose_synthesis_model([_resp("top", False)], "routed") == "routed"

        mock_settings.ARENA_SYNTHESIS_MODEL = "chair"
        assert engine._choose_synthesis_model(responses, "free") == "chair"

        mock_settings.ARENA_SYNTHESIS_MODEL = "not-enabled"
        assert engine._choose_synthesis_model(responses, "free") == "mid"


def test_aggregate_usage_call_sums_the_report_pipeline():
    from agents import UsageAccumulator, UsageCall
    from arena.engine import _aggregate_usage_call

    acc = UsageAccumulator()
    assert _aggregate_usage_call(acc) is None
    acc.add_call(UsageCall(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost_usd=0.1))
    acc.add_call(UsageCall(prompt_tokens=20, completion_tokens=10, total_tokens=30, cost_usd=0.2))
    call = _aggregate_usage_call(acc)
    assert call.total_tokens == 45
    assert call.prompt_tokens == 30
    assert round(call.cost_usd, 6) == 0.3
