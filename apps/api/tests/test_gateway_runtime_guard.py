import pytest


def _seed_gateway_identity(db_session, *, debate_id="gateway-guard"):
    from models import Debate, DebateAttempt, User

    user = User(
        id=f"user-{debate_id}",
        email=f"{debate_id}@example.com",
        password_hash="test",
    )
    debate = Debate(
        id=debate_id,
        prompt="gateway accounting test prompt",
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
    return user, debate, attempt


def test_failed_gateway_call_still_counts_tokens_and_cost(db_session):
    from model_gateway.runtime_guard import _persist_gateway_usage_sync
    from model_gateway.types import GatewayModelCallResult
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry
    from sqlmodel import select

    user, debate, attempt = _seed_gateway_identity(db_session)
    result = GatewayModelCallResult(
        content="partial",
        model_used="openai/gpt-4o-mini",
        provider="openai",
        prompt_tokens=40,
        completion_tokens=10,
        total_tokens=50,
        cost_usd=0.012,
        estimated_cost_usd=0.01,
        latency_ms=100,
        success=False,
        error_message="stream_active_stall",
        model_pool="arena_primary_pool",
        routing_policy="stream",
    )

    _persist_gateway_usage_sync(
        result=result,
        user_id=user.id,
        debate_id=debate.id,
        role="arena_stream",
        user_plan="free",
        preflight_estimate=0.02,
    )

    db_session.expire_all()
    usage_log = db_session.exec(
        select(LLMUsageLog).where(LLMUsageLog.debate_id == debate.id)
    ).first()
    assert usage_log is not None
    assert usage_log.success is False
    assert usage_log.total_tokens == 50
    assert usage_log.cost_usd == pytest.approx(0.012)
    assert usage_log.estimated_cost_usd == pytest.approx(0.02)

    token_ledger = db_session.exec(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.kind == "gateway_token_usage",
            UsageLedgerEntry.debate_id == debate.id,
        )
    ).first()
    assert token_ledger is not None
    assert token_ledger.status == "settled"
    assert token_ledger.amount == 50
    assert token_ledger.attempt_id == attempt.id

    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert counter is not None
    assert counter.tokens_used == 50


@pytest.mark.anyio
async def test_monthly_cost_guard_reads_persisted_actual_spend(db_session, monkeypatch):
    import model_gateway.costs as costs
    from model_gateway.runtime_guard import _persist_gateway_usage_sync
    from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

    user, debate, _attempt = _seed_gateway_identity(db_session, debate_id="monthly-spend")
    _persist_gateway_usage_sync(
        result=GatewayModelCallResult(
            content="ok",
            model_used="openai/gpt-4o-mini",
            provider="openai",
            total_tokens=100,
            cost_usd=0.04,
            estimated_cost_usd=0.04,
            success=True,
            model_pool="arena_primary_pool",
            routing_policy="direct",
        ),
        user_id=user.id,
        debate_id=debate.id,
        role="test",
        user_plan="free",
        preflight_estimate=0.04,
    )

    monkeypatch.setattr(costs, "MAX_MONTHLY_SAFETY_LIMIT_USD", 0.05)
    with pytest.raises(GatewayQuotaExceededError, match="monthly safety limit"):
        await costs.check_credit_and_cost_safety(
            user.id,
            "free",
            estimated_cost_usd=0.02,
            db_session=db_session,
        )


def test_atomic_reservation_is_visible_before_provider_and_settles_to_actual(db_session):
    from model_gateway.reservations import (
        reserve_gateway_budget_sync,
        settle_gateway_budget_sync,
    )
    from model_gateway.types import GatewayModelCallResult
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry
    from sqlmodel import select

    user, debate, _attempt = _seed_gateway_identity(db_session, debate_id="reservation-settle")
    reservation = reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="openai/gpt-4o-mini",
        role="arena_stream",
        user_plan="free",
        estimated_cost_usd=0.02,
        estimated_tokens=1000,
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
    assert log.cost_usd == pytest.approx(0.02)
    assert log.provider == "reservation"
    assert ledger.status == "reserved"
    assert ledger.amount == 1000
    assert counter.tokens_used == 1000

    settle_gateway_budget_sync(
        reservation,
        result=GatewayModelCallResult(
            content="ok",
            model_used="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=70,
            completion_tokens=30,
            total_tokens=100,
            cost_usd=0.005,
            estimated_cost_usd=0.02,
            success=True,
            model_pool="arena_primary_pool",
            routing_policy="stream",
        ),
        safe_error_message=None,
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
    assert log.cost_usd == pytest.approx(0.005)
    assert log.provider == "openai"
    assert log.total_tokens == 100
    assert ledger.status == "settled"
    assert ledger.amount == 100
    assert counter.tokens_used == 100


def test_second_cost_reservation_sees_first_pending_reservation(db_session, monkeypatch):
    import model_gateway.costs as costs
    from model_gateway.reservations import reserve_gateway_budget_sync
    from model_gateway.types import GatewayQuotaExceededError

    user, debate, _attempt = _seed_gateway_identity(db_session, debate_id="reservation-cost-race")
    monkeypatch.setattr(costs, "MAX_MONTHLY_SAFETY_LIMIT_USD", 0.03)

    reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="model-a",
        role="arena_stream",
        user_plan="free",
        estimated_cost_usd=0.02,
        estimated_tokens=10,
    )
    with pytest.raises(GatewayQuotaExceededError, match="monthly safety limit"):
        reserve_gateway_budget_sync(
            user_id=user.id,
            debate_id=debate.id,
            model_id="model-b",
            role="arena_stream",
            user_plan="free",
            estimated_cost_usd=0.02,
            estimated_tokens=10,
        )


@pytest.mark.anyio
async def test_legacy_monthly_check_does_not_double_count_current_reservation(
    db_session,
    monkeypatch,
):
    import model_gateway.costs as costs
    from model_gateway.reservations import reserve_gateway_budget_sync

    user, debate, _attempt = _seed_gateway_identity(db_session, debate_id="reservation-context")
    monkeypatch.setattr(costs, "MAX_MONTHLY_SAFETY_LIMIT_USD", 0.02)
    reservation = reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="model-a",
        role="producer",
        user_plan="free",
        estimated_cost_usd=0.02,
        estimated_tokens=10,
    )

    token = costs.bind_cost_reservation(user.id, reservation.reserved_cost_usd)
    try:
        # The reservation itself already occupies $0.02 in the table. The
        # legacy inner check must subtract that exact current reservation before
        # adding its older/smaller estimate, otherwise it rejects its own call.
        await costs.check_credit_and_cost_safety(
            user.id,
            "free",
            estimated_cost_usd=0.005,
            db_session=db_session,
        )
    finally:
        costs.reset_cost_reservation(token)


def test_terminal_attempt_applies_only_gateway_unaccounted_delta(db_session):
    from model_gateway.runtime_guard import _persist_gateway_usage_sync
    from model_gateway.types import GatewayModelCallResult
    from models import DebateAttempt, UsageCounter
    from sqlmodel import select
    from terminal_accounting_reconciler import ensure_token_accounting_once

    user, debate, attempt = _seed_gateway_identity(db_session, debate_id="gateway-delta")
    _persist_gateway_usage_sync(
        result=GatewayModelCallResult(
            content="ok",
            model_used="openai/gpt-4o-mini",
            provider="openai",
            total_tokens=200,
            cost_usd=0.01,
            success=True,
            model_pool="arena_primary_pool",
            routing_policy="direct",
        ),
        user_id=user.id,
        debate_id=debate.id,
        role="producer",
        user_plan="free",
        preflight_estimate=0.01,
    )

    db_session.expire_all()
    attempt = db_session.get(DebateAttempt, attempt.id)
    attempt.tokens_used = 300
    attempt.status = "completed"
    db_session.add(attempt)
    db_session.commit()

    assert ensure_token_accounting_once(
        db_session,
        debate=db_session.get(type(debate), debate.id),
        attempt=attempt,
    ) is True
    db_session.commit()

    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert counter is not None
    assert counter.tokens_used == 300


def test_terminal_attempt_does_not_double_count_unsettled_gateway_reservation(db_session):
    from model_gateway.reservations import reserve_gateway_budget_sync
    from models import DebateAttempt, UsageCounter
    from sqlmodel import select
    from terminal_accounting_reconciler import ensure_token_accounting_once

    user, debate, attempt = _seed_gateway_identity(db_session, debate_id="reserved-crash")
    reserve_gateway_budget_sync(
        user_id=user.id,
        debate_id=debate.id,
        model_id="model-a",
        role="producer",
        user_plan="free",
        estimated_cost_usd=0.01,
        estimated_tokens=300,
    )

    db_session.expire_all()
    attempt = db_session.get(DebateAttempt, attempt.id)
    attempt.tokens_used = 200
    attempt.status = "completed"
    db_session.add(attempt)
    db_session.commit()

    # Conservative reservation already charged 300. Terminal aggregate must not
    # add the 200 again after a crash before gateway settlement.
    assert ensure_token_accounting_once(
        db_session,
        debate=db_session.get(type(debate), debate.id),
        attempt=attempt,
    ) is False
    db_session.commit()
    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert counter.tokens_used == 300


@pytest.mark.anyio
async def test_gateway_persist_marker_suppresses_legacy_duplicate(monkeypatch):
    import model_gateway.runtime_guard as guard

    calls = []

    async def legacy(call_usage, **kwargs):
        calls.append((call_usage, kwargs))

    monkeypatch.setattr(guard, "_original_legacy_usage_persist", legacy)
    usage = type("Usage", (), {})()
    guard.mark_usage_call_persisted(usage)
    await guard._dedupe_legacy_usage_persist(
        usage,
        debate_id="d",
        user_id="u",
        role="test",
        latency_ms=1,
        success=True,
    )
    assert calls == []


def test_full_cost_estimate_includes_output_budget(monkeypatch):
    import model_gateway.runtime_guard as guard

    monkeypatch.setattr(guard, "_resolved_litellm_model", lambda _model: "unknown-model")
    estimate_small = guard.estimate_full_call_cost(
        messages=[{"role": "user", "content": "hello"}],
        model_id="unknown",
        max_tokens=10,
    )
    estimate_large = guard.estimate_full_call_cost(
        messages=[{"role": "user", "content": "hello"}],
        model_id="unknown",
        max_tokens=1000,
    )
    assert estimate_large > estimate_small
