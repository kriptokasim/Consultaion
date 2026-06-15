import logging
from datetime import datetime, timezone
from typing import Optional, List, Set
from sqlmodel import Session, select
from models import DebateContinuation
from database_async import async_session_scope
from exceptions import ContinuationTransitionError

logger = logging.getLogger(__name__)

ALLOWED_CONTINUATION_TRANSITIONS = {
    "requested": {"preflight_passed", "failed", "cancelled"},
    "preflight_passed": {"dispatched", "failed", "cancelled"},
    "dispatched": {"running", "failed", "cancelled"},
    "running": {"paused", "completed", "failed"},
    "paused": set(),
    "completed": set(),
    "failed": {"requested"},
    "cancelled": set(),
}


def _validate_transition(current_status: str, target_status: str) -> None:
    """Validate that a transition is allowed by the canonical transition map."""
    allowed = ALLOWED_CONTINUATION_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ContinuationTransitionError(
            continuation_id="",
            current_status=current_status,
            target_status=target_status,
            message=(
                f"Invalid continuation transition: {current_status} → {target_status}. "
                f"Allowed targets from '{current_status}': {allowed or '(none — terminal state)'}"
            ),
        )


def transition_continuation_sync(
    session: Session,
    continuation_id: str,
    expected_statuses: List[str],
    target_status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
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
        raise ContinuationTransitionError(
            continuation_id=continuation_id,
            current_status=continuation.status,
            target_status=target_status,
            message=(
                f"Invalid transition for continuation {continuation_id}: "
                f"current status '{continuation.status}' not in expected {expected_statuses}"
            ),
        )

    _validate_transition(continuation.status, target_status)

    _apply_continuation_updates(continuation, target_status, failure_code, failure_detail_safe)
    session.add(continuation)
    session.commit()
    session.refresh(continuation)
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
            raise ContinuationTransitionError(
                continuation_id=continuation_id,
                current_status=continuation.status,
                target_status=target_status,
                message=(
                    f"Invalid transition for continuation {continuation_id}: "
                    f"current status '{continuation.status}' not in expected {expected_statuses}"
                ),
            )

        _validate_transition(continuation.status, target_status)

        _apply_continuation_updates(continuation, target_status, failure_code, failure_detail_safe)
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
    elif status == "failed":
        continuation.failed_at = now
        continuation.failure_code = failure_code
        continuation.failure_detail_safe = failure_detail_safe
    elif status == "cancelled":
        continuation.cancelled_at = now
