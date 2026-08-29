import pytest


def _seed_retry_reservations(db_session):
    from models import Debate, UsageLedgerEntry, User

    user = User(
        id="retry-credit-user",
        email="retry-credit@example.com",
        password_hash="test",
        hosted_credits_limit=10,
        hosted_credits_used=2,
    )
    debate = Debate(
        id="retry-credit-debate",
        prompt="test",
        status="scheduled",
        user_id=user.id,
        run_attempt=2,
        credit_reservation_id="new-reservation",
    )
    old = UsageLedgerEntry(
        id="old-reservation",
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit_reserve:retry-credit-debate:a1:cnone",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 1, "continuation_id": None},
    )
    new = UsageLedgerEntry(
        id="new-reservation",
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit_reserve:retry-credit-debate:a2:cnone",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 2, "continuation_id": None},
    )
    db_session.add(user)
    db_session.add(debate)
    db_session.add(old)
    db_session.add(new)
    db_session.commit()
    return user, debate, old, new


def test_superseded_retry_refund_is_deferred_while_dispatch_unconfirmed(db_session):
    import retry_accounting_guard as guard

    _user, debate, old, _new = _seed_retry_reservations(db_session)

    assert guard._is_superseded_retry_refund(
        db_session,
        old.id,
        debate.id,
    ) is True

    # If compensation restores the prior pointer after a broker failure, the
    # prior reservation must still be active rather than already refunded.
    debate.credit_reservation_id = old.id
    debate.status = "perspectives_ready"
    db_session.add(debate)
    db_session.commit()

    assert guard._is_superseded_retry_refund(
        db_session,
        old.id,
        debate.id,
    ) is False


def test_successful_retry_handoff_refunds_only_noncurrent_attempt_reservation(
    db_session,
    monkeypatch,
):
    import billing.service as billing_service
    import retry_accounting_guard as guard
    from models import UsageLedgerEntry, User

    user, debate, old, new = _seed_retry_reservations(db_session)
    monkeypatch.setattr(guard, "_original_refund", billing_service.refund_hosted_credit)

    changed = guard._refund_superseded_attempt_reservations(debate.id)

    assert changed == 1
    db_session.expire_all()
    assert db_session.get(UsageLedgerEntry, old.id).status == "refunded"
    assert db_session.get(UsageLedgerEntry, new.id).status == "reserved"
    persisted_user = db_session.get(User, user.id)
    assert persisted_user.hosted_credits_used == 1


@pytest.mark.anyio
async def test_retry_cleanup_runs_only_after_successful_full_retry_dispatch(monkeypatch):
    import retry_accounting_guard as guard

    dispatch_calls = []
    cleanup_calls = []

    async def successful_dispatch(*args, **kwargs):
        dispatch_calls.append((args, kwargs))

    def cleanup(debate_id):
        cleanup_calls.append(debate_id)
        return 1

    monkeypatch.setattr(guard, "_original_dispatch", successful_dispatch)
    monkeypatch.setattr(guard, "_refund_superseded_attempt_reservations", cleanup)

    await guard._guarded_dispatch_debate_run(
        "debate-success",
        "prompt",
        "debate:debate-success",
        {},
        "model",
        resume=True,
        continuation_id=None,
    )

    assert len(dispatch_calls) == 1
    assert cleanup_calls == ["debate-success"]


@pytest.mark.anyio
async def test_failed_retry_dispatch_never_refunds_prior_attempt(monkeypatch):
    import retry_accounting_guard as guard

    cleanup_calls = []

    async def failed_dispatch(*_args, **_kwargs):
        raise RuntimeError("broker unavailable")

    def cleanup(debate_id):
        cleanup_calls.append(debate_id)
        return 1

    monkeypatch.setattr(guard, "_original_dispatch", failed_dispatch)
    monkeypatch.setattr(guard, "_refund_superseded_attempt_reservations", cleanup)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await guard._guarded_dispatch_debate_run(
            "debate-failed",
            "prompt",
            "debate:debate-failed",
            {},
            "model",
            resume=True,
            continuation_id=None,
        )

    assert cleanup_calls == []
