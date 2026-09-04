from __future__ import annotations

from fastapi import APIRouter, Depends
from models import (
    Debate,
    DebateAttempt,
    DebateContinuation,
    DebateStageCheckpoint,
    User,
    utcnow,
)
from sqlmodel import Session, select

from auth import get_current_user
from deps import get_session, get_sse_backend
from exceptions import NotFoundError, ValidationError
from routes.common import require_debate_mutation_access
from sse_backend import BaseSSEBackend
from utils.async_bridge import run_blocking

router = APIRouter()



def _cancel_transaction(debate_id: str, current_user: User, session: Session) -> tuple[str, int]:
    """Apply the complete cancellation/accounting transaction synchronously."""
    from billing.service import refund_hosted_credit
    from usage_limits import refund_run_slot

    debate = session.exec(
        select(Debate).where(Debate.id == debate_id).with_for_update()
    ).first()
    if debate is None:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    require_debate_mutation_access(debate, current_user, session)

    if debate.status in {"completed", "failed", "cancelled"}:
        raise ValidationError(
            message=f"Run is already terminal ({debate.status}).",
            code="debate.cancel_terminal",
            status_code=409,
        )
    if debate.status not in {"scheduled", "running"}:
        raise ValidationError(
            message=f"Run cannot be cancelled from state {debate.status}.",
            code="debate.cancel_invalid_state",
            status_code=409,
        )

    attempt = session.exec(
        select(DebateAttempt)
        .where(
            DebateAttempt.debate_id == debate_id,
            DebateAttempt.attempt_number == int(debate.run_attempt or 1),
        )
        .with_for_update()
    ).first()

    continuation = session.exec(
        select(DebateContinuation)
        .where(DebateContinuation.debate_id == debate_id)
        .where(
            DebateContinuation.status.in_(
                ["requested", "preflight_passed", "dispatched", "running"]
            )
        )
        .order_by(DebateContinuation.updated_at.desc())
        .with_for_update()
    ).first()

    # Compensations belong to the run's owner, not the actor performing the
    # cancellation (admins/team editors may cancel another user's run).
    owner_id = debate.user_id or current_user.id

    reservation_id = debate.credit_reservation_id
    if reservation_id:
        refund_hosted_credit(
            session,
            owner_id,
            reservation_id=reservation_id,
            debate_id=debate_id,
        )

    continuation_reservation_id = (
        continuation.credit_reservation_id if continuation is not None else None
    )
    if continuation_reservation_id and continuation_reservation_id != reservation_id:
        refund_hosted_credit(
            session,
            continuation.user_id or owner_id,
            reservation_id=continuation_reservation_id,
            debate_id=debate_id,
        )

    # Increment epoch before terminalizing so the old worker is fenced.
    debate.lease_epoch = int(debate.lease_epoch or 0) + 1
    debate.runner_id = None
    debate.lease_expires_at = None
    debate.credit_reservation_id = None
    debate.status = "cancelled"
    debate.updated_at = utcnow()
    session.add(debate)

    if attempt is not None and attempt.status not in {"completed", "failed", "cancelled"}:
        attempt.status = "cancelled"
        attempt.completed_at = utcnow()
        attempt.error_summary = "cancelled_by_user"
        session.add(attempt)

    checkpoints = session.exec(
        select(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == debate_id)
        .where(DebateStageCheckpoint.status.in_(["running", "scheduled", "queued"]))
    ).all()
    for checkpoint in checkpoints:
        checkpoint.status = "cancelled"
        checkpoint.completed_at = utcnow()
        session.add(checkpoint)

    if continuation is not None:
        continuation.status = "cancelled"
        continuation.cancelled_at = utcnow()
        continuation.updated_at = utcnow()
        session.add(continuation)

    session.commit()

    # Return the run slot in the same synchronous transaction boundary.
    refund_run_slot(session, owner_id)

    return debate_id, int(debate.run_attempt or 1)


@router.post("/debates/{debate_id}/cancel")
async def cancel_debate_run(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    """Cancel the active run and fence stale workers before terminal SSE."""
    cancelled_id, attempt_number = await run_blocking(
        _cancel_transaction,
        debate_id,
        current_user,
        session,
    )

    await sse_backend.publish(
        f"debate:{cancelled_id}",
        {
            "type": "cancelled",
            "contract_version": 1,
            "debate_id": str(cancelled_id),
            "run_attempt": attempt_number,
            "status": "cancelled",
            "reason": "cancelled_by_user",
            "partial_output_available": True,
        },
    )
    return {
        "id": cancelled_id,
        "status": "cancelled",
        "attempt_number": attempt_number,
        "partial_output_available": True,
    }
