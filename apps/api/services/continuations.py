import logging
from datetime import datetime, timezone
from typing import List, Optional

from database_async import async_session_scope
from exceptions import ContinuationTransitionError
from models import Debate, DebateContinuation
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

ALLOWED_CONTINUATION_TRANSITIONS = {
    "requested": {"preflight_passed", "failed", "cancelled"},
    # Inline dispatch moves directly into the orchestrator. There is no
    # durable queue hand-off to represent with ``dispatched``, so the runner
    # may claim a preflight-passed continuation directly as ``running``.
    # This also lets a Celery task recover if it was durably enqueued but the
    # route process died before persisting the dispatched timestamp.
    "preflight_passed": {"dispatched", "running", "failed", "cancelled"},
    "dispatched": {"running", "failed", "cancelled"},
    "running": {"paused", "completed", "failed"},
    "paused": set(),
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

# Older Compare/Conversation callers used these failure codes for every
# non-"completed" result. ``completed_with_warnings`` is a successful terminal
# product state, so persisting one of these continuations as failed creates an
# accounting contradiction: hosted-credit settlement keys off continuation
# status and would refund a run the product successfully delivered.
_PARTIAL_SUCCESS_FAILURE_CODES = frozenset({
    "compare_run_failed",
    "conversation_run_failed",
})


def _validate_transition(current_status: str, target_status: str) -> None:
    """Validate that a transition is allowed by the canonical transition map."""
    allowed = ALLOWED_CONTINUATION_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        from observability.metrics import record_continuation_transition_conflict
        record_continuation_transition_conflict(current_status, target_status)
        raise ContinuationTransitionError(
            continuation_id="",
            current_status=current_status,
            target_status=target_status,
            message=(
                f"Invalid continuation transition: {current_status} → {target_status}. "
                f"Allowed targets from '{current_status}': {allowed or '(none — terminal state)'}"
            ),
        )


def _reconcile_partial_success_target_sync(
    session: Session,
    continuation: DebateContinuation,
    target_status: str,
    failure_code: Optional[str],
    failure_detail_safe: Optional[str],
) -> tuple[str, Optional[str], Optional[str]]:
    if target_status != "failed" or failure_code not in _PARTIAL_SUCCESS_FAILURE_CODES:
        return target_status, failure_code, failure_detail_safe

    debate = session.get(Debate, continuation.debate_id)
    if debate and debate.status == "completed_with_warnings":
        logger.warning(
            "continuation.partial_success_reconciled continuation_id=%s debate_id=%s failure_code=%s",
            continuation.id,
            continuation.debate_id,
            failure_code,
        )
        return "completed", None, None
    return target_status, failure_code, failure_detail_safe


async def _reconcile_partial_success_target_async(
    session,
    continuation: DebateContinuation,
    target_status: str,
    failure_code: Optional[str],
    failure_detail_safe: Optional[str],
) -> tuple[str, Optional[str], Optional[str]]:
    if target_status != "failed" or failure_code not in _PARTIAL_SUCCESS_FAILURE_CODES:
        return target_status, failure_code, failure_detail_safe

    debate = await session.get(Debate, continuation.debate_id)
    if debate and debate.status == "completed_with_warnings":
        logger.warning(
            "continuation.partial_success_reconciled continuation_id=%s debate_id=%s failure_code=%s",
            continuation.id,
            continuation.debate_id,
            failure_code,
        )
        return "completed", None, None
    return target_status, failure_code, failure_detail_safe


def transition_continuation_sync(
    session: Session,
    continuation_id: str,
    expected_statuses: List[str],
    target_status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
    *,
    commit: bool = True,
) -> DebateContinuation:
    """Transition a specific continuation record atomically to target_status.

    Validates both the caller-provided expected statuses and the canonical
    transition map. Raises ContinuationTransitionError on conflict or not found.
    """
    stmt = (
        select(DebateContinuation)
        .where(DebateContinuation.id == continuation_id)
        .with_for_update()
    )
    continuation = session.exec(stmt).first()
    if not continuation:
        raise ContinuationTransitionError(
            continuation_id=continuation_id,
            current_status="not_found",
            target_status=target_status,
            message=f"Continuation record {continuation_id} not found",
        )

    if continuation.status not in expected_statuses:
        from observability.metrics import record_continuation_transition_conflict
        record_continuation_transition_conflict(continuation.status, target_status)
        raise ContinuationTransitionError(
            continuation_id=continuation_id,
            current_status=continuation.status,
            target_status=target_status,
            message=(
                f"Invalid transition for continuation {continuation_id}: "
                f"current status '{continuation.status}' not in expected {expected_statuses}"
            ),
        )

    target_status, failure_code, failure_detail_safe = _reconcile_partial_success_target_sync(
        session,
        continuation,
        target_status,
        failure_code,
        failure_detail_safe,
    )

    original_status = continuation.status
    _validate_transition(original_status, target_status)

    _apply_continuation_updates(continuation, target_status, failure_code, failure_detail_safe)

    from observability.metrics import record_continuation_transition
    record_continuation_transition(original_status, target_status)

    session.add(continuation)
    if commit:
        session.commit()
        session.refresh(continuation)
    else:
        session.flush()
    return continuation


async def transition_continuation_async(
    continuation_id: str,
    expected_statuses: List[str],
    target_status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> DebateContinuation:
    """Asynchronously transition a specific continuation record atomically to target_status.

    Validates both the caller-provided expected statuses and the canonical
    transition map. Raises ContinuationTransitionError on conflict or not found.
    """
    async with async_session_scope() as session:
        stmt = (
            select(DebateContinuation)
            .where(DebateContinuation.id == continuation_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        continuation = result.scalars().first()
        if not continuation:
            raise ContinuationTransitionError(
                continuation_id=continuation_id,
                current_status="not_found",
                target_status=target_status,
                message=f"Continuation record {continuation_id} not found",
            )

        if continuation.status not in expected_statuses:
            from observability.metrics import record_continuation_transition_conflict
            record_continuation_transition_conflict(continuation.status, target_status)
            raise ContinuationTransitionError(
                continuation_id=continuation_id,
                current_status=continuation.status,
                target_status=target_status,
                message=(
                    f"Invalid transition for continuation {continuation_id}: "
                    f"current status '{continuation.status}' not in expected {expected_statuses}"
                ),
            )

        target_status, failure_code, failure_detail_safe = await _reconcile_partial_success_target_async(
            session,
            continuation,
            target_status,
            failure_code,
            failure_detail_safe,
        )

        original_status = continuation.status
        _validate_transition(original_status, target_status)

        _apply_continuation_updates(continuation, target_status, failure_code, failure_detail_safe)

        from observability.metrics import record_continuation_transition
        record_continuation_transition(original_status, target_status)

        session.add(continuation)
        await session.commit()
        return continuation


def _apply_continuation_updates(
    continuation: DebateContinuation,
    status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc)
    continuation.status = status
    continuation.updated_at = now

    if status == "preflight_passed":
        continuation.preflight_passed_at = now
    elif status == "dispatched":
        continuation.dispatched_at = now
    elif status == "running":
        continuation.started_at = now
    elif status == "paused":
        continuation.paused_at = now
    elif status == "completed":
        continuation.completed_at = now
        # A successful terminal state must not retain stale failure metadata
        # from a caller that was normalized from partial success.
        continuation.failure_code = None
        continuation.failure_detail_safe = None
        continuation.failed_at = None
    elif status == "failed":
        continuation.failed_at = now
        continuation.failure_code = failure_code
        continuation.failure_detail_safe = failure_detail_safe
    elif status == "cancelled":
        continuation.cancelled_at = now
