from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from models import Debate, DebateContinuation, LLMUsageLog, User
from sqlalchemy.sql.dml import Update
from sqlmodel import Session, select


def test_continue_conditional_transition(authenticated_client, db_session):
    # Get user
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # 1. Test invalid source status: "queued"
    debate_queued = Debate(
        id="test-continue-queued",
        user_id=user.id,
        prompt="Test prompt",
        status="queued",
    )
    db_session.add(debate_queued)
    db_session.commit()

    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_queued.id}/continue")
        assert response.status_code == 400
        mock_dispatch.assert_not_called()

    # 2. Test valid source status: "perspectives_ready"
    debate_paused = Debate(
        id="test-continue-paused",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate_paused)
    db_session.commit()

    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_paused.id}/continue")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        mock_dispatch.assert_called_once_with(
            "test-continue-paused",
            "Test prompt",
            "debate:test-continue-paused",
            {},
            None,
            trace_id=None,
            resume=True,
            continuation_id=ANY,
        )

        # Check DB status is updated to scheduled
        db_session.refresh(debate_paused)
        assert debate_paused.status == "scheduled"

    # 3. Test sending again (now that it is "scheduled") -> should conflict
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_paused.id}/continue")
        assert response.status_code == 400
        mock_dispatch.assert_not_called()


def test_continue_idempotency_key(authenticated_client, db_session, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery")
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-idem",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    headers = {"X-Idempotency-Key": "test-idem-key-123"}

    # First call - should succeed and dispatch
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        assert response.status_code == 200
        mock_dispatch.assert_called_once()

        # Verify continuation record
        continuation = db_session.exec(
            select(DebateContinuation).where(
                DebateContinuation.debate_id == debate.id,
                DebateContinuation.idempotency_key == "test-idem-key-123"
            )
        ).first()
        assert continuation is not None
        assert continuation.status == "dispatched"

    # Second call (with same key) - should act as no-op and NOT dispatch again
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        assert response.status_code == 200
        # Debate status is currently scheduled, but continuation status is dispatched
        assert response.json()["status"] == "dispatched"
        mock_dispatch.assert_not_called()

    # If it is marked as failed, retry with same key should fail with 409
    old_cont_id = continuation.id
    continuation.status = "failed"
    db_session.add(continuation)
    db_session.commit()

    # Move debate back to failed so it's a valid source state
    debate.status = "failed"
    db_session.add(debate)
    db_session.commit()

    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "continuation.new_idempotency_key_required"
        assert response.json()["error"]["details"]["new_idempotency_key_required"] is True
        mock_dispatch.assert_not_called()

        # Verify the continuation record remained failed
        db_session.refresh(continuation)
        assert continuation.id == old_cont_id
        assert continuation.status == "failed"


def test_preflight_passed_scheduled_continuation_recovers_dispatch(
    authenticated_client,
    db_session,
    monkeypatch,
):
    """Retry closes the crash window after scheduling commit, before dispatch."""

    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery")

    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-continue-recover-scheduled",
        user_id=user.id,
        prompt="Recover this continuation",
        status="scheduled",
    )
    continuation = DebateContinuation(
        debate_id=debate.id,
        user_id=user.id,
        idempotency_key="recover-scheduled-key",
        status="preflight_passed",
        credit_reservation_id="durable-reservation-id",
    )
    db_session.add(debate)
    db_session.add(continuation)
    db_session.commit()

    headers = {"X-Idempotency-Key": continuation.idempotency_key}
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch, \
         patch("routes.debates.execution.check_continue_preflight") as mock_preflight, \
         patch("billing.service.reserve_hosted_credit") as mock_reserve:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers,
        )

    assert response.status_code == 200
    mock_preflight.assert_not_called()
    mock_reserve.assert_not_called()
    mock_dispatch.assert_called_once_with(
        debate.id,
        debate.prompt,
        f"debate:{debate.id}",
        {},
        None,
        trace_id=None,
        resume=True,
        continuation_id=continuation.id,
    )
    db_session.refresh(continuation)
    db_session.refresh(debate)
    assert continuation.status == "dispatched"
    assert continuation.credit_reservation_id == "durable-reservation-id"
    assert debate.status == "scheduled"


def test_inline_continuation_stays_resumable_until_background_task_starts(
    authenticated_client,
    db_session,
    monkeypatch,
):
    """A response/process crash before BackgroundTasks starts remains retryable."""

    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "inline")
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-inline-dispatch-crash-window",
        user_id=user.id,
        prompt="Keep inline dispatch resumable",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()
    headers = {"X-Idempotency-Key": "inline-dispatch-crash-key"}

    # Simulate a process that returns the response but never executes the
    # registered Starlette background task.
    with patch("starlette.background.BackgroundTasks.add_task") as add_task:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers,
        )

    assert response.status_code == 200
    add_task.assert_called_once()
    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
            DebateContinuation.idempotency_key == headers["X-Idempotency-Key"],
        )
    ).first()
    assert continuation is not None
    db_session.refresh(continuation)
    db_session.refresh(debate)
    assert continuation.status == "preflight_passed"
    assert debate.status == "scheduled"

    # The same key must recover the durable scheduled state and register work
    # again instead of early-returning a false dispatched acknowledgement.
    with patch("starlette.background.BackgroundTasks.add_task") as retry_add_task:
        retry = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers,
        )

    assert retry.status_code == 200
    retry_add_task.assert_called_once()


def test_celery_continuation_is_dispatched_only_after_enqueue_ack(
    authenticated_client,
    db_session,
    monkeypatch,
):
    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery")
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-celery-dispatch-order",
        user_id=user.id,
        prompt="Enqueue before acknowledge",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()
    observed_statuses = []

    async def observe_enqueue(*_args, **_kwargs):
        continuation = db_session.exec(
            select(DebateContinuation).where(
                DebateContinuation.debate_id == debate.id,
            )
        ).first()
        db_session.refresh(continuation)
        observed_statuses.append(continuation.status)

    with patch(
        "routes.debates.execution.dispatch_debate_run",
        new=AsyncMock(side_effect=observe_enqueue),
    ) as dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers={"X-Idempotency-Key": "celery-dispatch-order-key"},
        )

    assert response.status_code == 200
    dispatch.assert_awaited_once()
    assert observed_statuses == ["preflight_passed"]
    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
        )
    ).first()
    db_session.refresh(continuation)
    assert continuation.status == "dispatched"


def test_celery_enqueue_failure_never_publishes_dispatched(
    authenticated_client,
    db_session,
    monkeypatch,
):
    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery")
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-celery-enqueue-failure",
        user_id=user.id,
        prompt="Broker unavailable",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    with patch(
        "routes.debates.execution.dispatch_debate_run",
        new=AsyncMock(side_effect=RuntimeError("broker unavailable")),
    ):
        with pytest.raises(RuntimeError, match="broker unavailable"):
            authenticated_client.post(
                f"/api/v1/debates/{debate.id}/continue",
                headers={"X-Idempotency-Key": "celery-enqueue-failure-key"},
            )

    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
        )
    ).first()
    db_session.refresh(continuation)
    db_session.refresh(debate)
    assert continuation.status == "failed"
    assert continuation.failure_code == "debate.dispatch_failed"
    assert debate.status == "perspectives_ready"


def test_post_enqueue_status_failure_does_not_compensate_durable_task(
    authenticated_client,
    db_session,
    monkeypatch,
):
    from services import continuations as continuation_service

    from config import settings

    monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "celery")
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-celery-post-enqueue-transition-failure",
        user_id=user.id,
        prompt="Task is already durable",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()
    original_transition = continuation_service.transition_continuation_sync

    def fail_dispatched_transition(*args, **kwargs):
        target_status = args[3] if len(args) > 3 else kwargs.get("target_status")
        if target_status == "dispatched":
            raise RuntimeError("database unavailable after enqueue")
        return original_transition(*args, **kwargs)

    with patch(
        "routes.debates.execution.dispatch_debate_run",
        new=AsyncMock(),
    ) as dispatch, patch(
        "services.continuations.transition_continuation_sync",
        side_effect=fail_dispatched_transition,
    ):
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers={"X-Idempotency-Key": "post-enqueue-transition-failure-key"},
        )

    assert response.status_code == 200
    dispatch.assert_awaited_once()
    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
        )
    ).first()
    db_session.refresh(continuation)
    db_session.refresh(debate)
    assert continuation.status == "preflight_passed"
    assert debate.status == "scheduled"


def test_continue_schedule_conflict_marks_rolled_back_continuation_failed(
    authenticated_client,
    db_session,
    monkeypatch,
):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-continue-schedule-conflict",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    original_execute = Session.execute

    def execute_with_schedule_conflict(self, statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == Debate.__tablename__:
            return MagicMock(rowcount=0)
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", execute_with_schedule_conflict)
    headers = {"X-Idempotency-Key": "test-schedule-conflict-key"}

    response = authenticated_client.post(
        f"/api/v1/debates/{debate.id}/continue",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "debate.continue_conflict"

    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
            DebateContinuation.idempotency_key == "test-schedule-conflict-key",
        )
    ).first()
    assert continuation is not None
    assert continuation.status == "failed"
    assert continuation.failure_code == "debate.continue_conflict"

    replay = authenticated_client.post(
        f"/api/v1/debates/{debate.id}/continue",
        headers=headers,
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "continuation.new_idempotency_key_required"


def test_continue_preflight_budget(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create a debate with strict budget limit (cost = 1.0)
    debate = Debate(
        id="test-continue-budget",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
        config={"budget": {"max_cost_usd": 1.0, "max_tokens": 1000}}
    )
    db_session.add(debate)
    db_session.commit()

    # Case 1: Within budget -> should pass
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 200
        mock_dispatch.assert_called_once()

    # Move debate back to perspectives_ready for Case 2
    db_session.refresh(debate)
    debate.status = "perspectives_ready"
    db_session.add(debate)
    db_session.commit()

    # Add usage log that exceeds budget (e.g., cost_usd = 1.5)
    usage = LLMUsageLog(
        debate_id=debate.id,
        user_id=user.id,
        provider="openai",
        model="gpt-4o",
        prompt_tokens=500,
        completion_tokens=500,
        total_tokens=1000,
        cost_usd=1.5
    )
    db_session.add(usage)
    db_session.commit()

    # Case 2: Exceeded budget -> should fail with ValidationError
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 400
        assert "cost limit exceeded" in response.json()["error"]["message"]
        mock_dispatch.assert_not_called()


def test_continue_preflight_circuit_breaker(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-circuit",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    # Mock health state to indicate circuit breaker is open (unhealthy)
    with patch("parliament.provider_health.get_health_state") as mock_get_health, \
         patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        
        mock_health = MagicMock()
        mock_health.is_open.return_value = True
        mock_get_health.return_value = mock_health

        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 400
        assert "Circuit breaker open" in response.json()["error"]["message"]
        mock_dispatch.assert_not_called()


def test_retry_debate_run(authenticated_client, db_session):
    from models import DebateStageCheckpoint, Score, Vote
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create failed debate
    debate = Debate(
        id="test-retry-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="failed",
    )
    db_session.add(debate)
    db_session.commit()

    # Add checkpoints
    cp_draft = DebateStageCheckpoint(debate_id=debate.id, stage_key="draft", status="completed", input_hash="h1")
    cp_critique = DebateStageCheckpoint(debate_id=debate.id, stage_key="critique", status="completed", input_hash="h2")
    cp_judge = DebateStageCheckpoint(debate_id=debate.id, stage_key="judge", status="failed", input_hash="h3")
    
    db_session.add(cp_draft)
    db_session.add(cp_critique)
    db_session.add(cp_judge)
    
    # Add dummy scores/votes
    score = Score(debate_id=debate.id, persona="Debater", judge="Judge", score=8.5, rationale="rational")
    vote = Vote(debate_id=debate.id, method="plurality", rankings={"order": ["Debater"]})
    db_session.add(score)
    db_session.add(vote)
    
    db_session.commit()

    # Call /retry on "judge" stage
    with patch("debate_dispatch.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/retry",
            json={"stage_key": "judge"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        assert response.json()["retried_stage"] == "judge"
        mock_dispatch.assert_called_once()

        # Check DB updates (FH125 G-7 non-destructive retry):
        # The retried stage's checkpoint is invalidated, not deleted — prior
        # attempt evidence remains immutable and inspectable.
        cps = db_session.exec(select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate.id)).all()
        cp_status = {c.stage_key: c.status for c in cps}
        assert cp_status["draft"] == "completed"
        assert cp_status["critique"] == "completed"
        assert cp_status["judge"] == "invalidated"

        # Scores and votes from the failed attempt are retained as evidence
        scores = db_session.exec(select(Score).where(Score.debate_id == debate.id)).all()
        assert len(scores) == 1
        votes = db_session.exec(select(Vote).where(Vote.debate_id == debate.id)).all()
        assert len(votes) == 1

        # A DebateAttempt record tracks the new run attempt
        from models import DebateAttempt
        attempts = db_session.exec(select(DebateAttempt).where(DebateAttempt.debate_id == debate.id)).all()
        assert len(attempts) == 1
        assert attempts[0].status == "queued"

        # Debate status updated to scheduled
        db_session.refresh(debate)
        assert debate.status == "scheduled"


def test_continue_dispatch_failure_safety(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-fail-safety",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    headers = {"X-Idempotency-Key": "test-fail-safety-key"}

    # Mock BackgroundTasks.add_task to throw an error
    with patch("starlette.background.BackgroundTasks.add_task", side_effect=Exception("celery queue full")):
        with pytest.raises(Exception, match="celery queue full"):
            authenticated_client.post(
                f"/api/v1/debates/{debate.id}/continue",
                headers=headers
            )
        
    # Verify the database state was rolled back to perspectives_ready
    db_session.refresh(debate)
    assert debate.status == "perspectives_ready"

    # Verify continuation record is marked as failed
    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
            DebateContinuation.idempotency_key == "test-fail-safety-key"
        )
    ).first()
    assert continuation is not None
    assert continuation.status == "failed"
    assert continuation.failure_code == "debate.dispatch_failed"
    assert "celery queue full" in continuation.failure_detail_safe


def test_get_debate_continuation(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-get-continuation-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()
    
    continuation = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="get-test-key",
        status="requested",
        user_id=user.id
    )
    db_session.add(continuation)
    db_session.commit()
    
    # Try valid request
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/{continuation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["continuation_id"] == str(continuation.id)
    assert data["status"] == "requested"
    assert data["idempotency_key"] == "get-test-key"
    assert data["created"] is False

    # Try non-existent UUID
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    # Try invalid UUID string format
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/not-a-uuid")
    assert response.status_code == 404


def test_continue_retry_of_continuation_id(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-retry-of-cont-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    # Create terminal continuation
    failed_cont = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="failed-key-1",
        status="failed",
        user_id=user.id
    )
    db_session.add(failed_cont)
    db_session.commit()

    # Verify we can pass retry_of_continuation_id with a DIFFERENT idempotency key
    with patch("routes.debates.execution.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            json={"retry_of_continuation_id": failed_cont.id},
            headers={"X-Idempotency-Key": "new-key-2"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["retry_of_continuation_id"] == failed_cont.id
        assert data["idempotency_key"] == "new-key-2"
        mock_dispatch.assert_called_once()
