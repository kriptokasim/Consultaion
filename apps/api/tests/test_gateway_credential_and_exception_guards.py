import asyncio

import pytest


def _seed_identity(db_session, *, suffix: str):
    from models import Debate, DebateAttempt, User

    user = User(
        id=f"user-{suffix}",
        email=f"{suffix}@example.com",
        password_hash="test",
    )
    debate = Debate(
        id=f"debate-{suffix}",
        prompt="test",
        status="running",
        user_id=user.id,
        run_attempt=1,
    )
    attempt = DebateAttempt(
        debate_id=debate.id,
        attempt_number=1,
        status="running",
    )
    db_session.add_all([user, debate, attempt])
    db_session.commit()
    return user, debate


def test_shared_provider_circuit_does_not_block_user_byok(monkeypatch):
    import model_gateway.provider_health as health

    class FakeRedis:
        def get(self, _key):
            return "open"

    monkeypatch.setattr(health, "get_redis", lambda: FakeRedis())

    assert health.is_circuit_open("openai", credential_scope="server") is True
    assert health.is_circuit_open("openai", credential_scope="user") is False


def test_runtime_guard_disables_legacy_credential_blind_agent_circuit_gate(monkeypatch):
    import agents
    import model_gateway.runtime_exception_guard as exception_guard

    monkeypatch.setattr(exception_guard, "_installed", False)
    monkeypatch.setattr(agents, "is_circuit_open", lambda *_a, **_k: True)

    exception_guard.install_runtime_exception_guard()

    assert agents.is_circuit_open("openai", canonical_model_id="model-a") is False


@pytest.mark.anyio
async def test_generic_preprovider_exception_releases_cost_and_token_reservation(
    db_session,
    monkeypatch,
):
    import model_gateway.runtime_exception_guard as exception_guard
    import model_gateway.runtime_guard as runtime_guard
    from model_gateway.reservations import reserve_gateway_budget_sync
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry
    from sqlmodel import select

    user, debate = _seed_identity(db_session, suffix="preprovider-exception")
    reservation = reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="model-a",
        role="producer",
        user_plan="free",
        estimated_cost_usd=0.01,
        estimated_tokens=100,
    )

    async def fake_reserve_budget(**_kwargs):
        return 0.01, 100, reservation

    monkeypatch.setattr(runtime_guard, "_reserve_budget", fake_reserve_budget)
    monkeypatch.setattr(exception_guard, "_installed", False)
    exception_guard.install_runtime_exception_guard()

    async def fail_before_adapter():
        raise RuntimeError("pre-provider failure")

    with pytest.raises(RuntimeError, match="pre-provider failure"):
        await runtime_guard._execute_guarded_route(
            route_call=fail_before_adapter,
            user_id=user.id,
            debate_id=debate.id,
            model_id="model-a",
            role="producer",
            user_plan="free",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=100,
        )

    db_session.expire_all()
    log = db_session.get(LLMUsageLog, reservation.usage_log_id)
    ledger = db_session.get(UsageLedgerEntry, reservation.token_ledger_id)
    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert log.cost_usd == 0
    assert log.provider == "reservation_released"
    assert ledger.status == "refunded"
    assert counter.tokens_used == 0


@pytest.mark.anyio
async def test_preprovider_cancellation_releases_reservation(db_session, monkeypatch):
    import model_gateway.runtime_exception_guard as exception_guard
    import model_gateway.runtime_guard as runtime_guard
    from model_gateway.reservations import reserve_gateway_budget_sync
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry
    from sqlmodel import select

    user, debate = _seed_identity(db_session, suffix="preprovider-cancel")
    reservation = reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="model-a",
        role="producer",
        user_plan="free",
        estimated_cost_usd=0.01,
        estimated_tokens=100,
    )

    async def fake_reserve_budget(**_kwargs):
        return 0.01, 100, reservation

    monkeypatch.setattr(runtime_guard, "_reserve_budget", fake_reserve_budget)
    monkeypatch.setattr(exception_guard, "_installed", False)
    exception_guard.install_runtime_exception_guard()

    async def cancel_before_adapter():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await runtime_guard._execute_guarded_route(
            route_call=cancel_before_adapter,
            user_id=user.id,
            debate_id=debate.id,
            model_id="model-a",
            role="producer",
            user_plan="free",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=100,
        )

    db_session.expire_all()
    log = db_session.get(LLMUsageLog, reservation.usage_log_id)
    ledger = db_session.get(UsageLedgerEntry, reservation.token_ledger_id)
    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert log.cost_usd == 0
    assert ledger.status == "refunded"
    assert counter.tokens_used == 0
