from __future__ import annotations

from fastapi import APIRouter, Depends
from models import Debate, DebateAttempt, DebateStageCheckpoint, User, utcnow
from sqlmodel import Session, select

from auth import get_current_user
from deps import get_session, get_sse_backend
from exceptions import NotFoundError, ValidationError
from routes.common import require_debate_mutation_access
from sse_backend import BaseSSEBackend

router = APIRouter()


@router.post("/debates/{debate_id}/cancel")
async def cancel_debate_run(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    """Cancel the active run and fence any stale worker before publishing terminal state."""
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

    reservation_id = debate.credit_reservation_id
    if reservation_id:
        refund_hosted_credit(
            session,
            current_user.id,
            reservation_id=reservation_id,
            debate_id=debate_id,
        )

    # Epoch fencing is the execution cancellation primitive. A worker holding
    # the old lease may finish its current provider await, but all subsequent
    # DB/SSE writes fail ownership checks and cannot resurrect the run.
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

    session.commit()

    # The reservation has already been settled. The run slot is also returned
    # because cancellation is not a completed user-visible run.
    refund_run_slot(session, current_user.id)

    channel = f"debate:{debate_id}"
    await sse_backend.publish(
        channel,
        {
            "type": "cancelled",
            "contract_version": 1,
            "debate_id": str(debate_id),
            "run_attempt": int(debate.run_attempt or 1),
            "status": "cancelled",
            "reason": "cancelled_by_user",
            "partial_output_available": True,
        },
    )
    return {
        "id": debate_id,
        "status": "cancelled",
        "attempt_number": int(debate.run_attempt or 1),
        "partial_output_available": True,
    }
