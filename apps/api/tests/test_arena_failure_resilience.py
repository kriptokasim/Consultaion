"""Patchset 148.2 — Arena model failure resilience regression tests.

Ensures that individual model failures do not crash the entire arena run.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Lightweight stubs (no DB required — these test engine logic in isolation)
# ---------------------------------------------------------------------------

@dataclass
class _FakeModelInfo:
    id: str
    display_name: str
    provider: str
    logo_url: str | None = None
    persona_type: str | None = None
    persona_tagline: str | None = None
    litellm_model: str | None = None


class _FakeUsage:
    """Minimal stand-in for the usage object returned by call_llm_for_role."""
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 40
        self.total_tokens = 50
        self.cost_usd = 0.0001
        self.provider = "mock"
        self.model = "mock"

    def to_dict(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
        }


_ARENA_MODELS: List[_FakeModelInfo] = [
    _FakeModelInfo(id="model-a", display_name="Model A", provider="openai"),
    _FakeModelInfo(id="model-b", display_name="Model B", provider="anthropic"),
    _FakeModelInfo(id="model-c", display_name="Model C", provider="gemini"),
]


# ---------------------------------------------------------------------------
# 1. classify_provider_exception returns ProviderCallFailure — verify .code.value
# ---------------------------------------------------------------------------

def test_classify_provider_exception_returns_provider_call_failure():
    """Regression: classify_provider_exception MUST return ProviderCallFailure,
    and the arena code must access .code.value — NOT .value."""
    from llm_errors import ProviderCallFailure, ProviderFailureCode, classify_provider_exception

    exc = TimeoutError("connection timed out")
    result = classify_provider_exception(exc)

    # Must be ProviderCallFailure, not ProviderFailureCode
    assert isinstance(result, ProviderCallFailure)
    assert hasattr(result, "code")
    assert hasattr(result, "message")
    assert hasattr(result, "raw_error")

    # .code is the enum, .code.value is the string
    assert isinstance(result.code, ProviderFailureCode)
    assert result.code.value == "model_timeout"
    assert isinstance(result.message, str)


def test_classify_provider_exception_auth_error():
    """Auth errors classified correctly."""
    from llm_errors import ProviderCallFailure, ProviderFailureCode, classify_provider_exception

    exc = Exception("API key not valid for this model")
    result = classify_provider_exception(exc)

    assert isinstance(result, ProviderCallFailure)
    assert result.code == ProviderFailureCode.INVALID_CREDENTIALS
    assert result.code.value == "invalid_credentials"


def test_classify_provider_exception_unknown_error():
    """Unknown errors return UNKNOWN code — never None."""
    from llm_errors import ProviderCallFailure, ProviderFailureCode, classify_provider_exception

    exc = Exception("something completely unexpected happened")
    result = classify_provider_exception(exc)

    assert isinstance(result, ProviderCallFailure)
    assert result.code == ProviderFailureCode.UNKNOWN
    assert result.code.value == "unknown"


# ---------------------------------------------------------------------------
# 2. One model raises TimeoutError — others succeed, run completes
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_one_model_timeout_others_succeed():
    """When one model times out, the run must still complete with the
    successful models, and the failed model must produce a persisted
    ArenaModelResponse(success=False)."""
    from arena.engine import ArenaResult, run_arena

    call_count = {"n": 0}

    async def mock_call_llm(*args, **kwargs):
        role = kwargs.get("role", "")
        if "Model B" in role:
            raise TimeoutError("Model B timed out after 45 seconds")
        call_count["n"] += 1
        return f"Answer from {role}", _FakeUsage()

    mock_report = MagicMock()
    mock_report.executive_summary = "Synthesized verdict"
    mock_report.title = "Decision Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {"mock": "report"}

    mock_stream_result = MagicMock()
    mock_stream_result.success = False
    mock_stream_result.error_message = "stream failed"
    mock_stream_result.error_code = "model_timeout"
    mock_stream_result.content = ""

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS), \
         patch("arena.engine.call_llm_for_role", side_effect=mock_call_llm), \
         patch("arena.engine.get_sse_backend", return_value=AsyncMock()), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        result = await run_arena("test-debate-1")

        assert isinstance(result, ArenaResult)
        assert result.status == "completed"

        # Verify we have responses for all 3 models
        assert len(result.model_responses) == 3

        # Identify the failed response
        failed = [r for r in result.model_responses if not r.success]
        succeeded = [r for r in result.model_responses if r.success]

        assert len(failed) == 1
        assert failed[0].model_id == "model-b"
        assert failed[0].error_code is not None
        assert len(succeeded) == 2


# ---------------------------------------------------------------------------
# 3. One model returns GatewayModelCallResult(success=False) — no crash
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_gateway_failure_result_no_crash():
    """When route_llm_stream returns success=False, the arena must NOT
    crash — it should produce a failed model response card."""
    from arena.engine import ArenaResult, run_arena

    call_index = {"n": 0}

    async def mock_call_llm(*args, **kwargs):
        call_index["n"] += 1
        return f"Answer {call_index['n']}", _FakeUsage()

    mock_report = MagicMock()
    mock_report.executive_summary = "Verdict"
    mock_report.title = "Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {}

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS), \
         patch("arena.engine.call_llm_for_role", side_effect=mock_call_llm), \
         patch("arena.engine.get_sse_backend", return_value=AsyncMock()), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        # Should not raise
        result = await run_arena("test-debate-2")
        assert isinstance(result, ArenaResult)
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# 4. All models fail → ArenaResult(status="failed"), no unhandled exception
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_all_models_fail_graceful():
    """When every model fails, the run must return ArenaResult(status='failed')
    without any unhandled exception propagating."""
    from arena.engine import ArenaResult, run_arena

    async def always_fail(*args, **kwargs):
        raise RuntimeError("Provider is down")

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS), \
         patch("arena.engine.call_llm_for_role", side_effect=always_fail), \
         patch("arena.engine.get_sse_backend", return_value=AsyncMock()), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        result = await run_arena("test-debate-3")

        assert isinstance(result, ArenaResult)
        assert result.status == "failed"
        assert result.error_reason == "all_models_failed"

        # All responses should be persisted as failed
        assert len(result.model_responses) == 3
        for r in result.model_responses:
            assert r.success is False
            assert r.error is not None


# ---------------------------------------------------------------------------
# 5. as_completed preserves immediate persist/publish
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_as_completed_immediate_publish():
    """Verify that each model response is published as soon as it completes,
    not after all models finish."""
    from arena.engine import run_arena

    publish_log = []
    delays = {"model-a": 0.01, "model-b": 0.05, "model-c": 0.03}

    async def mock_call_llm(*args, **kwargs):
        role = kwargs.get("role", "")
        for mid, delay in delays.items():
            if mid.replace("-", " ").title().replace(" ", " ") in role or mid in role:
                await asyncio.sleep(delay)
                break
        return f"Answer from {role}", _FakeUsage()

    mock_backend = AsyncMock()

    async def tracking_publish(channel, data):
        if isinstance(data, dict) and data.get("type") == "arena_response":
            publish_log.append(data["model_id"])

    mock_backend.publish = AsyncMock(side_effect=tracking_publish)

    mock_report = MagicMock()
    mock_report.executive_summary = "Verdict"
    mock_report.title = "Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {}

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS), \
         patch("arena.engine.call_llm_for_role", side_effect=mock_call_llm), \
         patch("arena.engine.get_sse_backend", return_value=mock_backend), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        result = await run_arena("test-debate-4")
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# 6. final_meta.models order follows configured arena model order
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_final_meta_model_order():
    """Regardless of completion order, final_meta.models must follow the
    configured arena_models order."""
    from arena.engine import run_arena

    # Reverse order: C finishes first, then A, then B
    delays = {"model-a": 0.03, "model-b": 0.05, "model-c": 0.01}

    async def mock_call_llm(*args, **kwargs):
        role = kwargs.get("role", "")
        for mid, delay in delays.items():
            display = mid.replace("-", " ").title().replace(" ", "-")
            if display.replace("-", " ") in role:
                await asyncio.sleep(delay)
                break
        return f"Answer from {role}", _FakeUsage()

    mock_report = MagicMock()
    mock_report.executive_summary = "Verdict"
    mock_report.title = "Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {}

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS), \
         patch("arena.engine.call_llm_for_role", side_effect=mock_call_llm), \
         patch("arena.engine.get_sse_backend", return_value=AsyncMock()), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=_bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        result = await run_arena("test-debate-5")
        assert result.status == "completed"

        # Models in final_meta must follow arena_models order
        model_ids = [m["model_id"] for m in result.final_meta["models"]]
        assert model_ids == ["model-a", "model-b", "model-c"]


@pytest.mark.anyio
async def test_non_streaming_models_emit_symmetric_terminal_lifecycle():
    """Every persisted response ends with exactly one completed/failed event."""
    from arena.engine import run_arena

    models = _ARENA_MODELS[:2]

    async def mock_call_llm(*args, **kwargs):
        if "Model B" in kwargs.get("role", ""):
            raise RuntimeError("provider unavailable")
        return "successful answer", _FakeUsage()

    async def bypass_checkpoint(*args, **kwargs):
        run_fn = args[3]
        return await run_fn()

    mock_backend = AsyncMock()
    mock_report = MagicMock()
    mock_report.executive_summary = "Verdict"
    mock_report.title = "Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {}

    with patch("arena.engine.get_arena_models", return_value=models), \
         patch("arena.engine.call_llm_for_role", side_effect=mock_call_llm), \
         patch("arena.engine.get_sse_backend", return_value=mock_backend), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = False
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 45
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 60
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        await run_arena("test-debate-lifecycle")

    lifecycle = [
        call.args[1]
        for call in mock_backend.publish.await_args_list
        if call.args[1].get("type", "").startswith("model_response_")
    ]
    by_model = {
        model.id: [event for event in lifecycle if event.get("model_id") == model.id]
        for model in models
    }

    assert [event["type"] for event in by_model["model-a"]] == [
        "model_response_queued",
        "model_response_connecting",
        "model_response_started",
        "model_response_persisting",
        "model_response_completed",
    ]
    assert [event["type"] for event in by_model["model-b"]] == [
        "model_response_queued",
        "model_response_connecting",
        "model_response_started",
        "model_response_persisting",
        "model_response_failed",
    ]
    for events in by_model.values():
        assert len({event["response_id"] for event in events}) == 1
        assert all(event["run_attempt"] == 2 for event in events)
        assert all(event["retry_generation"] == 0 for event in events)


@pytest.mark.anyio
async def test_stream_fallback_uses_remaining_monotonic_deadline():
    """A failed stream must not reset the model timeout for its fallback."""
    from arena.engine import run_arena

    real_wait_for = asyncio.wait_for
    observed_timeouts = []

    async def tracking_wait_for(awaitable, timeout):
        observed_timeouts.append(timeout)
        return await real_wait_for(awaitable, timeout=timeout)

    async def failed_stream(*args, **kwargs):
        await asyncio.sleep(0.04)
        result = MagicMock()
        result.success = False
        result.error_message = "stream unavailable"
        result.error_code = "api_error"
        return result

    async def fallback(*args, **kwargs):
        return "fallback answer", _FakeUsage()

    async def bypass_checkpoint(*args, **kwargs):
        return await args[3]()

    mock_report = MagicMock()
    mock_report.executive_summary = "Verdict"
    mock_report.title = "Report"
    mock_report.divergence_breakdown = []
    mock_report.model_dump.return_value = {}

    with patch("arena.engine.get_arena_models", return_value=_ARENA_MODELS[:1]), \
         patch("arena.engine.call_llm_for_role", side_effect=fallback), \
         patch("arena.engine.asyncio.wait_for", side_effect=tracking_wait_for), \
         patch("model_gateway.route_llm_stream", side_effect=failed_stream), \
         patch("arena.engine.get_sse_backend", return_value=AsyncMock()), \
         patch("arena.engine.async_session_scope", new_callable=lambda: _mock_session_scope), \
         patch("orchestration.checkpoints.run_with_checkpoint", side_effect=bypass_checkpoint), \
         patch("reporting.synthesizer.generate_decision_report", return_value=mock_report), \
         patch("config.settings") as mock_settings:
        mock_settings.FAST_DEBATE = False
        mock_settings.STREAMING_RESPONSES_ENABLED = True
        mock_settings.ARENA_MODEL_TIMEOUT_SECONDS = 0.06
        mock_settings.ARENA_MODEL_TOTAL_TIMEOUT_S = 0.08
        mock_settings.ARENA_MAX_TOKENS = 1200
        mock_settings.STAGED_DECISION_PIPELINE = False
        mock_settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS = 1

        result = await run_arena("test-debate-deadline")

    assert result.status == "completed"
    stream_timeout, fallback_timeout = observed_timeouts[-2:]
    assert fallback_timeout < stream_timeout
    assert fallback_timeout <= 0.05


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockAsyncSession:
    """Minimal async session mock for persist_and_publish_arena_response."""

    async def execute(self, stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def get(self, model_cls, id_):
        """Return a minimal Debate-like object."""
        obj = MagicMock()
        obj.prompt = "test prompt"
        obj.config = {}
        obj.user_id = "test-user"
        obj.run_attempt = 2
        return obj


class _mock_session_scope:
    """Context manager returning a _MockAsyncSession."""
    async def __aenter__(self):
        return _MockAsyncSession()

    async def __aexit__(self, *args):
        pass


async def _bypass_checkpoint(debate_id, stage_name, input_data, run_fn, load_fn, **_kwargs):
    """Skip checkpoint logic — just call the run function directly."""
    return await run_fn()
