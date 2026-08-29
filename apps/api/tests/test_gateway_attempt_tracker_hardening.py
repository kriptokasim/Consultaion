import pytest


def _result(*, tokens=0, cost=0.0, provider="openai", success=True):
    from model_gateway.types import GatewayModelCallResult

    return GatewayModelCallResult(
        content="ok" if success else "",
        model_used="openai/gpt-4o-mini",
        provider=provider,
        prompt_tokens=tokens,
        completion_tokens=0,
        total_tokens=tokens,
        cost_usd=cost,
        estimated_cost_usd=cost,
        success=success,
        model_pool="test_pool",
        routing_policy="test",
    )


@pytest.mark.anyio
async def test_nested_stream_to_nonstream_fallback_is_one_provider_attempt(monkeypatch):
    from model_gateway.attempt_tracker import (
        GatewayAttemptContext,
        begin_adapter_attempt,
        bind_attempt_context,
        finish_adapter_attempt,
        reset_attempt_context,
    )
    import model_gateway.runtime_guard as guard

    monkeypatch.setattr(guard, "estimate_full_call_cost", lambda **_kwargs: 0.05)
    monkeypatch.setattr(guard, "estimate_full_call_tokens", lambda **_kwargs: 50)

    context = GatewayAttemptContext(
        user_id=None,
        debate_id="nested",
        user_plan="free",
        role="arena_stream",
        initial_cost_usd=0.10,
        initial_tokens=100,
    )
    token = bind_attempt_context(context)
    try:
        outer = await begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-a",
            max_tokens=100,
        )
        nested = await begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-a",
            max_tokens=100,
        )

        assert outer == 0
        assert nested == -1
        assert len(context.records) == 1

        # The inner adapter wrapper is bookkeeping-only; the outer wrapper owns
        # the provider attempt and records the returned non-stream result once.
        finish_adapter_attempt(nested, result=_result(tokens=25, cost=0.02))
        finish_adapter_attempt(outer, result=_result(tokens=25, cost=0.02))

        sequential = await begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-b",
            max_tokens=100,
        )
        assert sequential == 1
        assert len(context.records) == 2
        finish_adapter_attempt(sequential, result=_result(tokens=10, cost=0.01))
    finally:
        reset_attempt_context(token)


@pytest.mark.anyio
async def test_cumulative_provider_attempt_budget_uses_non_provider_control_signal(monkeypatch):
    from model_gateway.attempt_tracker import (
        GatewayAttemptContext,
        ProviderAttemptBudgetBlocked,
        begin_adapter_attempt,
        bind_attempt_context,
        finish_adapter_attempt,
        reset_attempt_context,
    )
    import model_gateway.runtime_guard as guard

    monkeypatch.setattr(guard, "estimate_full_call_cost", lambda **_kwargs: 0.25)
    monkeypatch.setattr(guard, "estimate_full_call_tokens", lambda **_kwargs: 50)

    context = GatewayAttemptContext(
        user_id=None,
        debate_id="cost-cap",
        user_plan="free",
        role="producer",
        initial_cost_usd=0.30,
        initial_tokens=100,
    )
    token = bind_attempt_context(context)
    try:
        first = await begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-a",
            max_tokens=100,
        )
        finish_adapter_attempt(first, result=_result(tokens=100, cost=0.30))

        # BaseException-derived control signal deliberately bypasses the legacy
        # route's broad ``except Exception`` so it cannot increment provider
        # circuit failures. The outer runtime remaps it to public quota error.
        with pytest.raises(ProviderAttemptBudgetBlocked, match="cumulative run cost"):
            await begin_adapter_attempt(
                messages=[{"role": "user", "content": "x"}],
                model_id="model-b",
                max_tokens=100,
            )
        assert len(context.records) == 1
    finally:
        reset_attempt_context(token)


def test_missing_provider_cost_keeps_conservative_cost_reservation():
    from model_gateway.attempt_tracker import (
        AttemptRecord,
        GatewayAttemptContext,
        aggregate_accounting_result,
    )

    provider_result = _result(tokens=50, cost=0.0, success=True)
    context = GatewayAttemptContext(
        user_id="u",
        debate_id="d",
        user_plan="free",
        role="producer",
        initial_cost_usd=0.20,
        initial_tokens=100,
        records=[
            AttemptRecord(
                reserved_cost_usd=0.20,
                reserved_tokens=100,
                result=provider_result,
            )
        ],
    )

    aggregated = aggregate_accounting_result(provider_result, context)
    assert aggregated.total_tokens == 50
    assert aggregated.cost_usd == pytest.approx(0.20)
    assert aggregated.estimated_cost_usd == pytest.approx(0.20)


def test_missing_provider_usage_keeps_conservative_token_reservation():
    from model_gateway.attempt_tracker import (
        AttemptRecord,
        GatewayAttemptContext,
        aggregate_accounting_result,
    )

    provider_result = _result(tokens=0, cost=0.01, success=True)
    context = GatewayAttemptContext(
        user_id="u",
        debate_id="d",
        user_plan="free",
        role="producer",
        initial_cost_usd=0.02,
        initial_tokens=120,
        records=[
            AttemptRecord(
                reserved_cost_usd=0.02,
                reserved_tokens=120,
                result=provider_result,
            )
        ],
    )

    aggregated = aggregate_accounting_result(provider_result, context)
    assert aggregated.total_tokens == 120
    assert aggregated.cost_usd == pytest.approx(0.01)
