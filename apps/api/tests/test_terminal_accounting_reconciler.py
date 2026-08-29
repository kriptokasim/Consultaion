def _seed_terminal_attempt(db_session, *, debate_id="acct-debate", tokens=321):
    from models import Debate, DebateAttempt, User

    user = User(
        id=f"user-{debate_id}",
        email=f"{debate_id}@example.com",
        password_hash="test",
        hosted_credits_limit=10,
        hosted_credits_used=0,
    )
    debate = Debate(
        id=debate_id,
        prompt="accounting test prompt",
        status="completed",
        user_id=user.id,
        run_attempt=1,
    )
    attempt = DebateAttempt(
        debate_id=debate.id,
        attempt_number=1,
        status="completed",
        tokens_used=tokens,
    )
    db_session.add_all([user, debate, attempt])
    db_session.commit()
    return user, debate, attempt


def test_daily_token_counter_is_applied_exactly_once(db_session):
    from models import UsageCounter, UsageLedgerEntry
    from sqlmodel import select
    from terminal_accounting_reconciler import ensure_token_accounting_once

    user, debate, attempt = _seed_terminal_attempt(db_session, tokens=321)

    assert ensure_token_accounting_once(
        db_session,
        debate=debate,
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
    assert counter.tokens_used == 321

    ledger = db_session.exec(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.idempotency_key == f"token_usage:{debate.id}:{attempt.id}"
        )
    ).first()
    assert ledger is not None
    assert ledger.status == "settled"
    assert ledger.meta["daily_counter_applied"] is True

    # Retry/reconciliation after a crash must not increment the daily counter a
    # second time.
    assert ensure_token_accounting_once(
        db_session,
        debate=debate,
        attempt=attempt,
    ) is False
    db_session.commit()
    db_session.refresh(counter)
    assert counter.tokens_used == 321


def test_reconciler_reconstructs_missing_token_accounting(db_session):
    from models import UsageCounter
    from sqlmodel import select
    from terminal_accounting_reconciler import reconcile_terminal_accounting_sync

    user, _debate, _attempt = _seed_terminal_attempt(
        db_session,
        debate_id="reconcile-token",
        tokens=444,
    )

    stats = reconcile_terminal_accounting_sync()

    assert stats["token_counters_applied"] == 1
    db_session.expire_all()
    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert counter is not None
    assert counter.tokens_used == 444


def test_terminal_success_settles_reserved_hosted_credit(db_session):
    from models import Debate, UsageLedgerEntry, User
    from terminal_accounting_reconciler import _settle_credit_entry

    user = User(
        id="credit-success-user",
        email="credit-success@example.com",
        password_hash="test",
        hosted_credits_limit=10,
        hosted_credits_used=1,
    )
    debate = Debate(
        id="credit-success",
        prompt="credit test prompt",
        status="completed_with_warnings",
        user_id=user.id,
        run_attempt=1,
        credit_reservation_id="credit-success-entry",
    )
    entry = UsageLedgerEntry(
        id="credit-success-entry",
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit_reserve:credit-success:a1:cnone",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 1, "continuation_id": None},
    )
    db_session.add_all([user, debate, entry])
    db_session.commit()

    assert _settle_credit_entry(db_session, entry) == "settled"
    db_session.commit()
    db_session.refresh(entry)
    db_session.refresh(user)
    assert entry.status == "settled"
    # Reservation already consumed the credit; successful settlement does not
    # decrement hosted_credits_used.
    assert user.hosted_credits_used == 1


def test_failed_continuation_refunds_its_own_reservation(db_session):
    from models import Debate, DebateContinuation, UsageLedgerEntry, User
    from terminal_accounting_reconciler import _settle_credit_entry

    user = User(
        id="credit-cont-user",
        email="credit-cont@example.com",
        password_hash="test",
        hosted_credits_limit=10,
        hosted_credits_used=1,
    )
    debate = Debate(
        id="credit-cont",
        prompt="credit continuation prompt",
        status="completed",
        user_id=user.id,
        run_attempt=1,
    )
    continuation = DebateContinuation(
        id="failed-continuation",
        debate_id=debate.id,
        idempotency_key="failed-cont-key",
        status="failed",
        user_id=user.id,
        credit_reservation_id="failed-cont-credit",
    )
    entry = UsageLedgerEntry(
        id="failed-cont-credit",
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key=f"credit_reserve:{debate.id}:a1:c{continuation.id}",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 1, "continuation_id": continuation.id},
    )
    db_session.add_all([user, debate, continuation, entry])
    db_session.commit()

    assert _settle_credit_entry(db_session, entry) == "refunded"
    db_session.commit()
    db_session.refresh(entry)
    db_session.refresh(user)
    assert entry.status == "refunded"
    assert user.hosted_credits_used == 0
