"""User-initiated Run cancellation.

Cancellation is a terminal product transition, not a client-only UI state. The
transaction invalidates execution ownership before returning so a stale worker
cannot persist or finalize after the user presses Stop. Redis receives a
best-effort mismatch tombstone to make hot streamed deltas observe the fence on
their next publish instead of waiting for the heartbeat interval.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from auth import get_current_user
from billing.service import refund_hosted_credit
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models import (
    Debate,
    DebateAttempt,
    DebateContinuation,
    DebateStageCheckpoint,
    User,
)
from routes.common import require_debate_mutation_access, require_schema_current
from sqlmodel import Session, select
from sse_backend import get_sse_backend

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_ACTIVE_STATUSES = {"queued", "scheduled", "running", "perspectives_ready"}
_FINAL_STATUSES = {"completed", "completed_with_warnings", "failed"}
_ACTIVE_CONTINUATION_STATUSES = {
    "requested",
    "preflight_passed",
    "dispatched",
    "running",
    "paused",
}


async def _publish_cancel_tombstone(debate_id: str, lease_epoch: int) -> None:
    """Replace the fast SSE lease mirror with an explicit mismatch marker.

    The database remains authoritative. This is only a latency optimization for
    high-frequency delta publishers. A retry/acquire overwrites the marker with
    the new owner+epoch.
    """
    try:
        from orchestration.execution_lease_mirror import mirror_key
        from redis_pool import get_async_redis_client

        client = get_async_redis_client()
        if client is None:
            return
        ttl = max(int(getattr(settings, "LEASE_SECONDS", 60)) + 5, 5)
        for attempt in range(3):
            try:
                await client.set(
                    mirror_key(debate_id),
                    f"cancelled|{int(lease_epoch)}",
                    ex=ttl,
                )
                return
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.05 * (attempt + 1))
    except Exception:
        logger.warning(
            "debate.cancel.mirror_invalidation_failed debate_id=%s epoch=%s",
            debate_id,
            lease_epoch,
            exc_info=True,
        )


def _refund_credit_if_reserved(
    session: Session,
    *,
    user_id: str | None,
    reservation_id: str | None,
    debate_id: str,
) -> bool:
    if not user_id or not reservation_id:
        return False
    return refund_hosted_credit(
        session,
        user_id,
        reservation_id=reservation_id,
        debate_id=debate_id,
    )


@router.post("/debates/{debate_id}/cancel")
async def cancel_debate_run(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _schema_ok: None = Depends(require_schema_current),
):
    now = datetime.now(timezone.utc)

    # Lock the product row so cancellation is atomic with any concurrent
    # finalization/fenced persistence transaction.
    debate = session.exec(
        select(Debate).where(Debate.id == debate_id).with_for_update()
    ).first()
    debate = require_debate_mutation_access(debate, current_user, session)

    if debate.status == "cancelled":
        return {
            "id": debate.id,
            "status": "cancelled",
            "already_cancelled": True,
        }

    if debate.status in _FINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is already terminal with status '{debate.status}'.",
        )
    if debate.status not in _ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run cannot be stopped from status '{debate.status}'.",
        )

    old_epoch = int(debate.lease_epoch or 0)
    cancelled_epoch = old_epoch + 1
    attempt_number = int(debate.run_attempt or 0)

    # Product state and fencing identity are committed together. Bumping the
    # epoch makes every pre-cancel owner stale even before its next heartbeat.
    debate.status = "cancelled"
    debate.updated_at = now
    debate.runner_id = None
    debate.execution_owner_id = None
    debate.lease_expires_at = None
    debate.lease_epoch = cancelled_epoch
    debate.final_meta = {
        **(debate.final_meta or {}),
        "cancelled_by": "user",
        "cancelled_at": now.isoformat(),
        "cancelled_attempt": attempt_number or None,
    }

    # Hosted credits represent the run reservation, not already-incurred model
    # tokens/cost. Refund the active reservation exactly once; provider usage
    # recorded before Stop remains charged/accounted.
    _refund_credit_if_reserved(
        session,
        user_id=debate.user_id,
        reservation_id=debate.credit_reservation_id,
        debate_id=debate.id,
    )
    debate.credit_reservation_id = None
    session.add(debate)

    if attempt_number > 0:
        attempt = session.exec(
            select(DebateAttempt)
            .where(
                DebateAttempt.debate_id == debate.id,
                DebateAttempt.attempt_number == attempt_number,
            )
            .with_for_update()
        ).first()
        if attempt is not None and attempt.status not in {
            "completed",
            "completed_with_warnings",
            "failed",
            "cancelled",
        }:
            attempt.status = "cancelled"
            attempt.completed_at = now
            attempt.error_summary = "cancelled_by_user"
            session.add(attempt)

    # A cancelled logical run must not leave resumable stage ownership behind.
    checkpoints = session.exec(
        select(DebateStageCheckpoint).where(
            DebateStageCheckpoint.debate_id == debate.id,
            DebateStageCheckpoint.status.in_(["pending", "running"]),
        )
    ).all()
    for checkpoint in checkpoints:
        checkpoint.status = "invalidated"
        checkpoint.updated_at = now
        checkpoint.owner_id = None
        checkpoint.lease_epoch = None
        checkpoint.error_code = "cancelled_by_user"
        checkpoint.error_message = "Run cancelled by user."
        session.add(checkpoint)

    # Continuations have their own hosted-credit reservations. Terminalize and
    # compensate any active continuation in the same transaction.
    continuations = session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
            DebateContinuation.status.in_(list(_ACTIVE_CONTINUATION_STATUSES)),
        )
    ).all()
    for continuation in continuations:
        _refund_credit_if_reserved(
            session,
            user_id=continuation.user_id or debate.user_id,
            reservation_id=continuation.credit_reservation_id,
            debate_id=debate.id,
        )
        continuation.credit_reservation_id = None
        continuation.status = "cancelled"
        continuation.updated_at = now
        continuation.cancelled_at = now
        continuation.failure_code = "cancelled_by_user"
        continuation.failure_detail_safe = "Run cancelled by user."
        session.add(continuation)

    session.commit()

    # Hot SSE publishers normally observe this mismatch on their very next
    # chunk. If Redis is unavailable, DB fencing and the heartbeat still remain
    # authoritative.
    await _publish_cancel_tombstone(debate.id, cancelled_epoch)

    # Existing clients already treat debate_failed as a terminal transport
    # boundary and immediately rehydrate durable state. Carry status=cancelled
    # explicitly so this is not a product failure; a versioned debate_cancelled
    # event can replace this compatibility envelope once all clients consume it.
    try:
        backend = get_sse_backend()
        await backend.publish(
            f"debate:{debate.id}",
            {
                "type": "debate_failed",
                "debate_id": debate.id,
                "status": "cancelled",
                "reason": "cancelled_by_user",
                "payload": {
                    "status": "cancelled",
                    "reason": "cancelled_by_user",
                    "message": "Run stopped by user.",
                },
            },
        )
    except Exception:
        logger.warning(
            "debate.cancel.terminal_publish_failed debate_id=%s",
            debate.id,
            exc_info=True,
        )

    logger.info(
        "debate.cancelled debate_id=%s user_id=%s epoch=%s",
        debate.id,
        current_user.id,
        cancelled_epoch,
    )
    return {
        "id": debate.id,
        "status": "cancelled",
        "already_cancelled": False,
    }
