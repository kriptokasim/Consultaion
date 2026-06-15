import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Session, select
from models import DebateContinuation
from database_async import async_session_scope
from exceptions import ContinuationTransitionError

logger = logging.getLogger(__name__)

def transition_continuation_sync(
    session: Session,
    continuation_id: str,
    expected_statuses: List[str],
    target_status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> DebateContinuation:
    """Transition a specific continuation record atomically to target_status.

    Verifies the record's current status is in expected_statuses.
    Raises ContinuationTransitionError on conflict or if not found.
    """
    stmt = (
        select(DebateContinuation)
        .where(DebateContinuation.id == continuation_id)
        .with_for_update()  # Lock the row for safety
    )
    continuation = session.exec(stmt).first()
    if not continuation:
        raise ContinuationTransitionError(
            continuation_id=continuation_id,
            current_status="not_found",
            target_status=target_status,
            message=f"Continuation record {continuation_id} not found"
        )

    if continuation.status not in expected_statuses:
        raise ContinuationTransitionError(
            continuation_id=continuation_id,
            current_status=continuation.status,
            target_status=target_status,
            message=(
                f"Invalid transition for continuation {continuation_id}: "
                f"current status '{continuation.status}' not in expected {expected_statuses}"
            )
        )

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

    Verifies the record's current status is in expected_statuses.
    Raises ContinuationTransitionError on conflict or if not found.
    """
    async with async_session_scope() as session:
        # We need to perform this in a transaction block
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
                message=f"Continuation record {continuation_id} not found"
            )

        if continuation.status not in expected_statuses:
            raise ContinuationTransitionError(
                continuation_id=continuation_id,
                current_status=continuation.status,
                target_status=target_status,
                message=(
                    f"Invalid transition for continuation {continuation_id}: "
                    f"current status '{continuation.status}' not in expected {expected_statuses}"
                )
            )

        _apply_continuation_updates(continuation, target_status, failure_code, failure_detail_safe)
        session.add(continuation)
        await session.commit()
        # Create a new non-bound instance or return refreshed from async session safely
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
    elif status == "completed":
        continuation.completed_at = now
    elif status == "failed":
        continuation.failed_at = now
        continuation.failure_code = failure_code
        continuation.failure_detail_safe = failure_detail_safe
    elif status == "cancelled":
        continuation.cancelled_at = now
