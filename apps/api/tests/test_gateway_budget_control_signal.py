import pytest


@pytest.mark.anyio
async def test_fallback_budget_block_bypasses_legacy_provider_exception_catcher(monkeypatch):
    import model_gateway.runtime_exception_guard as exception_guard
    import model_gateway.runtime_guard as runtime_guard
    from model_gateway.attempt_tracker import begin_adapter_attempt, finish_adapter_attempt
    from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

    async def fake_reserve_budget(**_kwargs):
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


@pytest.mark.anyio
async def test_fallback_accounting_failure_bypasses_provider_exception_catcher(monkeypatch):
    import model_gateway.attempt_tracker as tracker
    import model_gateway.runtime_exception_guard as exception_guard
    import model_gateway.runtime_guard as runtime_guard
    from model_gateway.reservations import GatewayBudgetReservation
    from model_gateway.types import GatewayModelCallResult

    reservation = GatewayBudgetReservation(
        usage_log_id="missing-usage-log",
        token_ledger_id="missing-token-ledger",
        user_id="user-a",
        reserved_cost_usd=0.05,
        reserved_tokens=100,
    )

    async def fake_reserve_budget(**_kwargs):
        return 0.05, 100, reservation

    def broken_extension(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(runtime_guard, "_reserve_budget", fake_reserve_budget)
    monkeypatch.setattr(runtime_guard, "estimate_full_call_cost", lambda **_kwargs: 0.01)
    monkeypatch.setattr(runtime_guard, "estimate_full_call_tokens", lambda **_kwargs: 25)
    monkeypatch.setattr(tracker, "_extend_reservation_sync", broken_extension)
    monkeypatch.setattr(exception_guard, "_installed", False)
    exception_guard.install_runtime_exception_guard()

    legacy_provider_exception_caught = False

    async def synthetic_legacy_route():
        nonlocal legacy_provider_exception_caught
        first = await tracker.begin_adapter_attempt(
            messages=[{"role": "user", "content": "x"}],
            model_id="model-a",
            max_tokens=100,
        )
        tracker.finish_adapter_attempt(
            first,
            result=GatewayModelCallResult(
                content="",
                model_used="model-a",
                provider="openai",
                prompt_tokens=10,
                completion_tokens=10,
                total_tokens=20,
                cost_usd=0.005,
                estimated_cost_usd=0.005,
                success=False,
                error_message="primary failed",
                model_pool="test",
                routing_policy="test",
            ),
        )
        try:
            await tracker.begin_adapter_attempt(
                messages=[{"role": "user", "content": "x"}],
                model_id="model-b",
                max_tokens=100,
            )
        except Exception:
            legacy_provider_exception_caught = True
            raise
        raise AssertionError("accounting control did not block the fallback")

    with pytest.raises(RuntimeError, match="usage accounting"):
        await runtime_guard._execute_guarded_route(
            route_call=synthetic_legacy_route,
            user_id=None,
            debate_id="accounting-control",
            model_id="model-a",
            role="producer",
            user_plan="free",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=100,
        )

    assert legacy_provider_exception_caught is False
