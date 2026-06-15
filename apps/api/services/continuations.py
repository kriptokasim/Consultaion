import logging
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select
from models import DebateContinuation
from database_async import async_session_scope

logger = logging.getLogger(__name__)

def update_continuation_sync(
    session: Session,
    debate_id: str,
    status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> Optional[DebateContinuation]:
    """Synchronously update the status of the latest continuation record for this debate."""
    try:
        stmt = (
            select(DebateContinuation)
            .where(DebateContinuation.debate_id == debate_id)
            .order_by(DebateContinuation.created_at.desc())
            .limit(1)
        )
        continuation = session.exec(stmt).first()
        if continuation:
            _apply_continuation_updates(continuation, status, failure_code, failure_detail_safe)
            session.add(continuation)
            session.commit()
            session.refresh(continuation)
            return continuation
    except Exception as e:
        logger.warning(f"Failed to update continuation status (sync) for debate {debate_id} to {status}: {e}")
    return None

async def update_continuation_async(
    debate_id: str,
    status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> Optional[DebateContinuation]:
    """Asynchronously update the status of the latest continuation record for this debate."""
    try:
        async with async_session_scope() as session:
            stmt = (
                select(DebateContinuation)
                .where(DebateContinuation.debate_id == debate_id)
                .order_by(DebateContinuation.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            continuation = result.scalars().first()
            if continuation:
                _apply_continuation_updates(continuation, status, failure_code, failure_detail_safe)
                session.add(continuation)
                await session.commit()
                return continuation
    except Exception as e:
        logger.warning(f"Failed to update continuation status (async) for debate {debate_id} to {status}: {e}")
    return None

def _apply_continuation_updates(
    continuation: DebateContinuation,
    status: str,
    failure_code: Optional[str] = None,
    failure_detail_safe: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc)
    continuation.status = status
    continuation.updated_at = now
    
    if status == "dispatched":
        continuation.dispatched_at = now
    elif status == "running":
        continuation.started_at = now
    elif status == "completed":
        continuation.completed_at = now
    elif status == "failed":
        continuation.failed_at = now
        continuation.failure_code = failure_code
        continuation.failure_detail_safe = failure_detail_safe
