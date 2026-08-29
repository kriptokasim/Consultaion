import pytest


@pytest.mark.anyio
async def test_fallback_budget_block_bypasses_legacy_provider_exception_catcher(monkeypatch):
    import model_gateway.runtime_exception_guard as exception_guard
    import model_gateway.runtime_guard as runtime_guard
    from model_gateway.attempt_tracker import begin_adapter_attempt, finish_adapter_attempt
    from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

    async def fake_reserve_budget(**_kwargs):
        # Initial invocation itself is allowed; the second provider attempt will
        # push the same logical gateway invocation beyond the per-run cap.
        return 0.30, 100, None

    monkeypatch.setattr(runtime_guard, "_reserve_budget", fake_reserve_budget)
    monkeypatch.setattr(runtime_guard, "estimate_full_call_cost", lambda **_kwargs: 0.25)
    monkeypatch.setattr(runtime_guard, "estimate_full_call_tokens", lambda **_kwargs: 50)
    monkeypatch.setattr(exception_guard, "_installed", False)
    exception_guard.install_runtime_exception_guard()

    legacy_provider_exception_caught = False

    async def synthetic_legacy_route():
        nonlocal legacy_provider_exception_caught
        first = await begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-a",
            max_tokens=100,
        )
        finish_adapter_attempt(
            first,
            result=GatewayModelCallResult(
                content="",
                model_used="model-a",
                provider="openai",
                prompt_tokens=50,
                completion_tokens=50,
                total_tokens=100,
                cost_usd=0.30,
                estimated_cost_usd=0.30,
                success=False,
                error_message="primary failed",
                model_pool="test",
                routing_policy="test",
            ),
        )
        try:
            # This mirrors the adapter call inside the historical route's broad
            # provider ``except Exception`` block.
            await begin_adapter_attempt(
                messages=[{"role": "user", "content": "x"}],
                model_id="model-b",
                max_tokens=100,
            )
        except Exception:
            legacy_provider_exception_caught = True
            raise
        raise AssertionError("budget control did not block the fallback")

    with pytest.raises(GatewayQuotaExceededError, match="cumulative run cost"):
        await runtime_guard._execute_guarded_route(
            route_call=synthetic_legacy_route,
            user_id=None,
            debate_id="budget-control",
            model_id="model-a",
            role="producer",
            user_plan="free",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=100,
        )

    assert legacy_provider_exception_caught is False
