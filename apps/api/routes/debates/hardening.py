from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Optional

from auth import get_current_user, get_current_user_flexible
from channels import debate_channel_id
from deps import get_session, get_sse_backend
from exceptions import NotFoundError, ValidationError
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from models import (
    Debate,
    DebateAttempt,
    DebateStageCheckpoint,
    Message,
    User,
    utcnow,
)
from schemas import DebateCreate
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend

from config import settings
from routes.common import require_debate_mutation_access, require_schema_current
from routes.debates.crud import create_debate as _legacy_create_debate
from routes.debates.execution import check_continue_preflight
from routes.debates.schemas import RetryAgentRequest, RetryRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class _CapturedTask:
    func: Any
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class _TaskCapture:
    """Capture Starlette background work until the request is safe to hand off."""

    def __init__(self) -> None:
        self.tasks: list[_CapturedTask] = []

    def add_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.tasks.append(_CapturedTask(func=func, args=args, kwargs=kwargs))


async def _invoke_task(task: _CapturedTask) -> None:
    result = task.func(*task.args, **task.kwargs)
    if inspect.isawaitable(result):
        await result


def _response_debate_id(response: Any) -> str | None:
    if isinstance(response, dict):
        value = response.get("id")
        return str(value) if value else None
    value = getattr(response, "id", None)
    return str(value) if value else None


def _compensate_created_run(
    session: Session,
    *,
    debate_id: str,
    user_id: str,
) -> None:
    """Reverse a committed create when Celery never acknowledged the hand-off."""
    from billing.service import get_or_create_usage, refund_hosted_credit
    from usage_limits import refund_run_slot

    session.rollback()
    debate = session.exec(
        select(Debate).where(Debate.id == debate_id).with_for_update()
    ).first()
    reservation_id = debate.credit_reservation_id if debate else None
    if debate is not None:
        debate.status = "failed"
        debate.updated_at = utcnow()
        debate.credit_reservation_id = None
        session.add(debate)

    attempt = session.exec(
        select(DebateAttempt).where(
            DebateAttempt.debate_id == debate_id,
            DebateAttempt.attempt_number == 1,
        )
    ).first()
    if attempt is not None and attempt.status not in {"completed", "failed", "cancelled"}:
        attempt.status = "failed"
        attempt.completed_at = utcnow()
        attempt.error_summary = "dispatch_failed"
        session.add(attempt)

    usage = get_or_create_usage(session, user_id)
    usage.debates_created = max(0, int(usage.debates_created or 0) - 1)
    session.add(usage)
    if reservation_id:
        refund_hosted_credit(
            session,
            user_id,
            reservation_id=reservation_id,
            debate_id=debate_id,
        )
    session.commit()
    refund_run_slot(session, user_id)


@router.post("/debates")
async def create_debate_hardened(
    body: DebateCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user_flexible),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    """Preserve canonical create validation while making Celery hand-off durable."""
    capture = _TaskCapture()
    response = await _legacy_create_debate(
        body=body,
        background_tasks=capture,  # type: ignore[arg-type]
        request=request,
        session=session,
        current_user=current_user,
        sse_backend=sse_backend,
    )

    if settings.DISABLE_AUTORUN or not capture.tasks:
        return response

    if (settings.DEBATE_DISPATCH_MODE or "inline").lower() != "celery":
        for task in capture.tasks:
            background_tasks.add_task(task.func, *task.args, **task.kwargs)
        return response

    debate_id = _response_debate_id(response)
    try:
        for task in capture.tasks:
            await _invoke_task(task)
    except Exception as exc:
        logger.exception("Celery hand-off failed for newly created debate %s", debate_id)
        if debate_id:
            _compensate_created_run(
                session,
                debate_id=debate_id,
                user_id=current_user.id,
            )
        raise ValidationError(
            message="Debate could not be scheduled. Please try again.",
            code="debate.dispatch_failed",
            status_code=503,
        ) from exc
    return response


def _retry_needs_hosted_credit(session: Session, user: User, debate: Debate) -> bool:
    from billing.service import get_active_plan
    from parliament.model_registry import resolve_model_info

    plan = get_active_plan(session, user.id)
    if not plan.is_default_free:
        return False
    if debate.mode == "arena":
        return True

    model_ids: list[str] = []
    if debate.model_id:
        model_ids.append(debate.model_id)
    panel = debate.panel_config or {}
    if isinstance(panel, dict):
        for seat in panel.get("seats", []) or []:
            if isinstance(seat, dict) and seat.get("model"):
                model_ids.append(str(seat["model"]))
    return any(
        (info := resolve_model_info(model_id)) is not None
        and getattr(info, "tier", "standard") == "advanced"
        for model_id in model_ids
    )


def _clone_arena_perspectives(
    session: Session,
    *,
    debate_id: str,
    source_attempt: int,
    target_attempt: int,
    target_attempt_id: str,
) -> int:
    rows = list(
        session.exec(
            select(Message)
            .where(Message.debate_id == debate_id)
            .where(Message.role == "arena_response")
            .order_by(Message.created_at.asc(), Message.id.asc())
        ).all()
    )
    latest: dict[str, Message] = {}
    generations: dict[str, int] = {}
    for row in rows:
        meta = row.meta or {}
        if int(meta.get("run_attempt", 1) or 1) != source_attempt:
            continue
        model_id = str(meta.get("model_id") or row.persona or "").strip()
        if not model_id:
            continue
        generation = int(meta.get("retry_generation", 0) or 0)
        if model_id not in latest or generation >= generations[model_id]:
            latest[model_id] = row
            generations[model_id] = generation

    for model_id, row in latest.items():
        meta = dict(row.meta or {})
        meta.update(
            {
                "run_attempt": target_attempt,
                "retry_generation": 0,
                "usage_call": None,
                "reused_from_attempt": source_attempt,
            }
        )
        session.add(
            Message(
                debate_id=debate_id,
                attempt_id=target_attempt_id,
                response_id=f"resp-{debate_id}-a{target_attempt}-g0-{model_id}",
                round_index=row.round_index,
                role="arena_response",
                persona=row.persona,
                content=row.content,
                meta=meta,
            )
        )
    return len(latest)


def _resolve_retry_stage(
    session: Session,
    debate_id: str,
    requested_stage: str | None,
) -> str | None:
    if requested_stage:
        return requested_stage
    failed = session.exec(
        select(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == debate_id)
        .where(DebateStageCheckpoint.status == "failed")
        .order_by(DebateStageCheckpoint.started_at.desc())
    ).first()
    if failed:
        return failed.stage_key
    latest = session.exec(
        select(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == debate_id)
        .order_by(DebateStageCheckpoint.started_at.desc())
    ).first()
    return latest.stage_key if latest else None


async def _schedule_retry(
    *,
    debate_id: str,
    requested_stage: str | None,
    background_tasks: BackgroundTasks,
    session: Session,
    current_user: User,
    sse_backend: BaseSSEBackend,
) -> dict[str, Any]:
    from billing.service import refund_hosted_credit, reserve_hosted_credit
    from debate_dispatch import dispatch_debate_run
    from orchestration.stage_graph import get_stages_to_invalidate
    from usage_limits import refund_run_slot, reserve_run_slot

    require_schema_current(session)
    debate = session.exec(
        select(Debate).where(Debate.id == debate_id).with_for_update()
    ).first()
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)
    if debate.status in {"scheduled", "running"}:
        raise ValidationError(
            message="A run is already scheduled or active for this debate",
            code="debate.retry_conflict",
            status_code=409,
        )

    check_continue_preflight(debate, current_user, session)
    stage_key = _resolve_retry_stage(session, debate_id, requested_stage)
    stages_to_clear = list(get_stages_to_invalidate(stage_key)) if stage_key else []
    source_attempt = max(int(debate.run_attempt or 0), 1)
    next_attempt = source_attempt + 1
    prior_status = debate.status
    prior_credit_reservation_id = debate.credit_reservation_id
    checkpoint_states: dict[str, str] = {}
    reservation_id: str | None = None

    try:
        reserve_run_slot(session, current_user.id, commit=False)
        if _retry_needs_hosted_credit(session, current_user, debate):
            reservation_id = reserve_hosted_credit(
                session,
                current_user.id,
                debate_id=debate_id,
                run_attempt=next_attempt,
            )

        attempt = DebateAttempt(
            debate_id=debate_id,
            attempt_number=next_attempt,
            status="queued",
            model_id=debate.model_id,
            created_at=utcnow(),
        )
        session.add(attempt)
        session.flush()

        if debate.mode == "arena" and "arena_perspectives" not in stages_to_clear:
            if _clone_arena_perspectives(
                session,
                debate_id=debate_id,
                source_attempt=source_attempt,
                target_attempt=next_attempt,
                target_attempt_id=attempt.id,
            ) == 0:
                stages_to_clear.extend(get_stages_to_invalidate("arena_perspectives"))

        if stages_to_clear:
            checkpoints = list(
                session.exec(
                    select(DebateStageCheckpoint)
                    .where(DebateStageCheckpoint.debate_id == debate_id)
                    .where(DebateStageCheckpoint.stage_key.in_(set(stages_to_clear)))
                ).all()
            )
            for checkpoint in checkpoints:
                checkpoint_states[checkpoint.id] = checkpoint.status
                checkpoint.status = "invalidated"
                session.add(checkpoint)

        channel_id = debate_channel_id(debate_id)
        await sse_backend.create_channel(channel_id)
        debate.status = "scheduled"
        debate.updated_at = utcnow()
        debate.credit_reservation_id = reservation_id
        session.add(debate)
        session.commit()
    except Exception:
        session.rollback()
        raise

    dispatch_args = (
        debate_id,
        debate.prompt,
        channel_id,
        debate.config or {},
        debate.model_id,
    )
    dispatch_kwargs = {"trace_id": None, "resume": True}
    try:
        if (settings.DEBATE_DISPATCH_MODE or "inline").lower() == "celery":
            await dispatch_debate_run(*dispatch_args, **dispatch_kwargs)
        else:
            background_tasks.add_task(dispatch_debate_run, *dispatch_args, **dispatch_kwargs)
    except Exception as exc:
        session.rollback()
        locked = session.exec(
            select(Debate).where(Debate.id == debate_id).with_for_update()
        ).first()
        if locked is not None:
            locked.status = prior_status
            locked.updated_at = utcnow()
            locked.credit_reservation_id = prior_credit_reservation_id
            session.add(locked)

        attempt = session.exec(
            select(DebateAttempt).where(
                DebateAttempt.debate_id == debate_id,
                DebateAttempt.attempt_number == next_attempt,
            )
        ).first()
        if attempt is not None:
            attempt.status = "failed"
            attempt.completed_at = utcnow()
            attempt.error_summary = "dispatch_failed"
            session.add(attempt)

        for checkpoint_id, previous_status in checkpoint_states.items():
            checkpoint = session.get(DebateStageCheckpoint, checkpoint_id)
            if checkpoint is not None:
                checkpoint.status = previous_status
                session.add(checkpoint)

        if reservation_id:
            refund_hosted_credit(
                session,
                current_user.id,
                reservation_id=reservation_id,
                debate_id=debate_id,
            )
        session.commit()
        refund_run_slot(session, current_user.id)
        raise ValidationError(
            message="Retry could not be scheduled. Please try again.",
            code="debate.dispatch_failed",
            status_code=503,
        ) from exc

    return {
        "id": debate_id,
        "status": "scheduled",
        "retried_stage": stage_key,
        "attempt_number": next_attempt,
    }


@router.post("/debates/{debate_id}/retry")
async def retry_debate_run_hardened(
    debate_id: str,
    background_tasks: BackgroundTasks,
    body: Optional[RetryRequest] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    return await _schedule_retry(
        debate_id=debate_id,
        requested_stage=body.stage_key if body else None,
        background_tasks=background_tasks,
        session=session,
        current_user=current_user,
        sse_backend=sse_backend,
    )


@router.post("/debates/{debate_id}/retry-agent")
async def retry_agent_hardened(
    debate_id: str,
    body: RetryAgentRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    require_debate_mutation_access(debate, current_user, session)
    stage = "arena_perspectives" if debate.mode == "arena" else "draft"
    logger.info(
        "Coherent full retry requested from agent card debate=%s persona=%s stage=%s",
        debate_id,
        body.persona,
        stage,
    )
    return await _schedule_retry(
        debate_id=debate_id,
        requested_stage=stage,
        background_tasks=background_tasks,
        session=session,
        current_user=current_user,
        sse_backend=sse_backend,
    )
