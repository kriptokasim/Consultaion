import logging
import uuid
from typing import Optional

import sqlalchemy as sa
from auth import get_current_user
from channels import debate_channel_id
from debate_dispatch import dispatch_debate_run
from deps import get_session, get_sse_backend
from exceptions import (
    NotFoundError,
    ValidationError,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from models import Debate, DebateContinuation, Message, User, utcnow
from parliament.model_registry import get_default_model, list_enabled_models
from schemas import (
    ContinuationRequest,
    ContinuationResponse,
)
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend

from config import settings
from routes.common import (
    require_debate_access,
    require_debate_mutation_access,
    require_schema_current,
)
from routes.debates.schemas import ContinuationResolveRequest, RetryAgentRequest, RetryRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def check_continue_preflight(debate: Debate, current_user: User, session: Session):
    """
    Validates token quotas, budget limits (max_cost_usd, max_tokens),
    and provider/model health before allowing a debate run to continue.
    """
    # 1. Token quota check
    from usage_limits import QuotaExceededError, check_quota
    estimated_tokens = 3000  # Average continue uses ~3k tokens
    try:
        check_quota(session, current_user, required_tokens=estimated_tokens)
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "kind": exc.kind,
                "limit": exc.limit,
                "used": exc.used,
            }
        ) from exc

    # 2. Budget limits validation (max_cost_usd, max_tokens)
    config = debate.config or {}
    budget = config.get("budget", {})
    max_cost_usd = budget.get("max_cost_usd")
    max_tokens = budget.get("max_tokens")

    if max_cost_usd is not None or max_tokens is not None:
        from models import LLMUsageLog
        usage_stmt = select(
            sa.func.sum(LLMUsageLog.cost_usd).label("total_cost"),
            sa.func.sum(LLMUsageLog.total_tokens).label("total_tokens")
        ).where(LLMUsageLog.debate_id == debate.id)
        usage_res = session.execute(usage_stmt).first()
        cost_used = usage_res[0] if usage_res and usage_res[0] is not None else 0.0
        tokens_used = usage_res[1] if usage_res and usage_res[1] is not None else 0

        if max_cost_usd is not None and cost_used >= max_cost_usd:
            raise ValidationError(
                message=f"Debate cost limit exceeded: {cost_used:.4f} USD >= {max_cost_usd:.4f} USD",
                code="debate.budget_exceeded"
            )
        if max_tokens is not None and tokens_used >= max_tokens:
            raise ValidationError(
                message=f"Debate token limit exceeded: {tokens_used} >= {max_tokens}",
                code="debate.budget_exceeded"
            )

    # 3. Model/Provider health check
    from datetime import datetime, timezone

    from parliament.provider_health import get_health_state

    enabled_models = {m.id: m for m in list_enabled_models()}
    target_model_id = debate.model_id or get_default_model().id
    target_model_info = enabled_models.get(target_model_id)

    if target_model_info:
        provider_name = getattr(target_model_info.provider, "value", str(target_model_info.provider)) if hasattr(target_model_info, "provider") else "unknown"
        target_model = target_model_info.litellm_model
        now = datetime.now(timezone.utc)
        health_state = get_health_state(provider_name, target_model)
        if health_state.is_open(now):
            raise ValidationError(
                message=f"Circuit breaker open for provider '{provider_name}' and model '{target_model}'. Model is currently unhealthy.",
                code="provider.unhealthy"
            )


def _retry_needs_hosted_credit(session: Session, current_user: User, debate: Debate) -> bool:
    from billing.service import get_active_plan
    from parliament.model_registry import resolve_model_info

    plan = get_active_plan(session, current_user.id)
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
    for model_id in model_ids:
        info = resolve_model_info(model_id)
        if info is not None and getattr(info, "tier", "standard") == "advanced":
            return True
    return False


def _reserve_retry_billing(
    session: Session,
    current_user: User,
    debate: Debate,
    *,
    next_attempt: int,
) -> str | None:
    """Reserve all billable-run entitlements before any retry provider call."""
    from billing.service import reserve_hosted_credit
    from usage_limits import refund_run_slot, reserve_run_slot

    check_continue_preflight(debate, current_user, session)
    reserve_run_slot(session, current_user.id)
    try:
        increment_debate_usage(session, current_user.id)
        if _retry_needs_hosted_credit(session, current_user, debate):
            return reserve_hosted_credit(
                session,
                current_user.id,
                debate_id=debate.id,
                run_attempt=next_attempt,
            )
        return None
    except Exception:
        session.rollback()
        refund_run_slot(session, current_user.id)
        raise


def _refund_committed_retry_billing(
    session: Session,
    current_user: User,
    debate: Debate,
    *,
    reservation_id: str | None,
) -> None:
    from billing.service import refund_hosted_credit
    from usage_limits import refund_run_slot

    if reservation_id:
        refund_hosted_credit(
            session,
            current_user.id,
            reservation_id=reservation_id,
            debate_id=debate.id,
        )
    decrement_debate_usage(session, current_user.id)
    session.commit()
    refund_run_slot(session, current_user.id)


def _retry_needs_hosted_credit(session: Session, current_user: User, debate: Debate) -> bool:
    from billing.service import get_active_plan
    from parliament.model_registry import resolve_model_info

    plan = get_active_plan(session, current_user.id)
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
    for model_id in model_ids:
        info = resolve_model_info(model_id)
        if info is not None and getattr(info, "tier", "standard") == "advanced":
            return True
    return False


def _reserve_retry_billing(
    session: Session,
    current_user: User,
    debate: Debate,
    *,
    next_attempt: int,
) -> str | None:
    """Reserve all billable-run entitlements before any retry provider call."""
    from billing.service import increment_debate_usage, reserve_hosted_credit
    from usage_limits import refund_run_slot, reserve_run_slot

    check_continue_preflight(debate, current_user, session)
    reserve_run_slot(session, current_user.id)
    try:
        increment_debate_usage(session, current_user.id)
        if _retry_needs_hosted_credit(session, current_user, debate):
            return reserve_hosted_credit(
                session,
                current_user.id,
                debate_id=debate.id,
                run_attempt=next_attempt,
            )
        return None
    except Exception:
        session.rollback()
        refund_run_slot(session, current_user.id)
        raise


def _refund_committed_retry_billing(
    session: Session,
    current_user: User,
    debate: Debate,
    *,
    reservation_id: str | None,
) -> None:
    from billing.service import decrement_debate_usage, refund_hosted_credit
    from usage_limits import refund_run_slot

    if reservation_id:
        refund_hosted_credit(
            session,
            current_user.id,
            reservation_id=reservation_id,
            debate_id=debate.id,
        )
    decrement_debate_usage(session, current_user.id)
    session.commit()
    refund_run_slot(session, current_user.id)


@router.post("/debates/{debate_id}/start")
async def start_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Set correlation context for this request
    from correlation import create_child_context, get_correlation_context
    ctx = get_correlation_context()
    if ctx:
        ctx = create_child_context(
            user_id=current_user.id if current_user else None,
            debate_id=debate_id,
        )

    if not settings.DISABLE_AUTORUN:
        raise ValidationError(message="Manual start is disabled", code="debate.manual_start_disabled")
    debate = session.get(Debate, debate_id)
    debate = require_debate_mutation_access(debate, current_user, session)
    if debate.status not in {"queued", "failed"}:
        raise ValidationError(message="Debate already started", code="debate.already_started")

    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)
    background_tasks.add_task(
        dispatch_debate_run,
        debate_id,
        debate.prompt,
        channel_id,
        debate.config or {},
        debate.model_id,
    )
    debate.status = "scheduled"
    session.add(debate)
    session.commit()
    
    from log_config import log_event
    log_fields = {
        "debate_id": debate_id,
        "user_id": current_user.id if current_user else None,
        "model_id": debate.model_id,
    }
    if ctx:
        log_fields.update(ctx.to_log_fields())
    log_event("debate.started_manually", **log_fields)

    from audit import record_audit
    record_audit(
        "debate_manual_start",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        meta=ctx.to_log_fields() if ctx else None,
        session=session,
    )
    return {"id": debate_id, "status": "scheduled"}


@router.post("/debates/{debate_id}/continue")
async def continue_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    body: Optional[ContinuationRequest] = None,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Set correlation context for this request
    from correlation import create_child_context, get_correlation_context
    ctx = get_correlation_context()
    if ctx:
        ctx = create_child_context(
            user_id=current_user.id if current_user else None,
            debate_id=debate_id,
        )

    require_schema_current(session)
    # Load debate and verify mutation access
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)

    retry_of_continuation_id = body.retry_of_continuation_id if body else None
    if retry_of_continuation_id:
        ref_cont = session.get(DebateContinuation, retry_of_continuation_id)
        if not ref_cont or ref_cont.debate_id != debate_id:
            raise NotFoundError(message="Referenced continuation not found", code="continuation.not_found")
        if ref_cont.status not in {"failed", "cancelled", "completed"}:
            raise ValidationError(
                message="Referenced continuation is not in a terminal state",
                code="continuation.not_terminal",
                status_code=400
            )
        if x_idempotency_key and ref_cont.idempotency_key == x_idempotency_key:
            raise ValidationError(
                message="Idempotency key must differ from the referenced continuation's key",
                code="continuation.duplicate_idempotency_key",
                status_code=400
            )

    # 1. Idempotency Check & Continuation record setup
    continuation_record = None
    if x_idempotency_key:
        stmt_chk = select(DebateContinuation).where(
            DebateContinuation.debate_id == debate_id,
            DebateContinuation.idempotency_key == x_idempotency_key
        )
        continuation_record = session.execute(stmt_chk).scalars().first()
        if continuation_record:
            # Only terminal or in-flight-beyond-preflight statuses are safe to
            # early-return. "requested" and "preflight_passed" may be orphaned
            # (crash after commit but before scheduling) and must be resumed.
            if continuation_record.status in {"dispatched", "running", "completed", "paused"}:
                return ContinuationResponse(
                    continuation_id=str(continuation_record.id),
                    debate_id=debate_id,
                    status=continuation_record.status,
                    debate_status=debate.status,
                    idempotency_key=continuation_record.idempotency_key,
                    created=False,
                    retry_of_continuation_id=continuation_record.retry_of_continuation_id,
                )
            if continuation_record.status in {"failed", "cancelled"}:
                raise ValidationError(
                    message="The previous continuation attempt failed or was cancelled. A new idempotency key is required.",
                    code="continuation.new_idempotency_key_required",
                    status_code=409,
                    details={"new_idempotency_key_required": True}
                )
            # "requested" or "preflight_passed" — resume the flow below.
            # Lock the row to prevent concurrent retries from double-dispatching.
            stmt_lock = (
                select(DebateContinuation)
                .where(DebateContinuation.id == continuation_record.id)
                .with_for_update()
            )
            continuation_record = session.execute(stmt_lock).scalars().first()
            if not continuation_record:
                raise NotFoundError(message="Continuation disappeared during resume", code="continuation.not_found")
            # Re-check status after acquiring lock — another worker may have progressed it.
            if continuation_record.status in {"dispatched", "running", "completed", "paused"}:
                return ContinuationResponse(
                    continuation_id=str(continuation_record.id),
                    debate_id=debate_id,
                    status=continuation_record.status,
                    debate_status=debate.status,
                    idempotency_key=continuation_record.idempotency_key,
                    created=False,
                    retry_of_continuation_id=continuation_record.retry_of_continuation_id,
                )
            if continuation_record.status in {"failed", "cancelled"}:
                raise ValidationError(
                    message="The previous continuation attempt failed or was cancelled. A new idempotency key is required.",
                    code="continuation.new_idempotency_key_required",
                    status_code=409,
                    details={"new_idempotency_key_required": True}
                )
            # Status is still "requested" or "preflight_passed" — resume below.
            logger.info(
                "Resuming orphaned continuation %s (status=%s) for debate %s",
                continuation_record.id, continuation_record.status, debate_id,
            )
        else:
            continuation_record = DebateContinuation(
                debate_id=debate_id,
                idempotency_key=x_idempotency_key,
                status="requested",
                user_id=current_user.id if current_user else None,
                target=debate.model_id,
                requested_at=sa.func.now(),
                retry_of_continuation_id=retry_of_continuation_id,
            )
            session.add(continuation_record)
            try:
                session.commit()
            except sa.exc.IntegrityError:
                session.rollback()
                continuation_record = session.execute(stmt_chk).scalars().first()
                if continuation_record and continuation_record.status in {"dispatched", "running", "completed", "paused"}:
                    return ContinuationResponse(
                        continuation_id=str(continuation_record.id),
                        debate_id=debate_id,
                        status=continuation_record.status,
                        debate_status=debate.status,
                        idempotency_key=continuation_record.idempotency_key,
                        created=False,
                        retry_of_continuation_id=continuation_record.retry_of_continuation_id,
                    )
                # If found in requested/preflight_passed after integrity error, resume it.
                if continuation_record and continuation_record.status in {"requested", "preflight_passed"}:
                    stmt_lock = (
                        select(DebateContinuation)
                        .where(DebateContinuation.id == continuation_record.id)
                        .with_for_update()
                    )
                    continuation_record = session.execute(stmt_lock).scalars().first()
                    if not continuation_record:
                        raise NotFoundError(
                            message="Continuation disappeared during resume",
                            code="continuation.not_found",
                        ) from None
                    if continuation_record.status in {"dispatched", "running", "completed", "paused"}:
                        return ContinuationResponse(
                            continuation_id=str(continuation_record.id),
                            debate_id=debate_id,
                            status=continuation_record.status,
                            debate_status=debate.status,
                            idempotency_key=continuation_record.idempotency_key,
                            created=False,
                            retry_of_continuation_id=continuation_record.retry_of_continuation_id,
                        )
                    logger.info(
                        "Resuming orphaned continuation %s (status=%s) for debate %s after integrity error",
                        continuation_record.id, continuation_record.status, debate_id,
                    )
                elif continuation_record and continuation_record.status in {"failed", "cancelled"}:
                    raise ValidationError(
                        message="The previous continuation attempt failed or was cancelled. A new idempotency key is required.",
                        code="continuation.new_idempotency_key_required",
                        status_code=409,
                        details={"new_idempotency_key_required": True}
                    ) from None
    else:
        continuation_record = DebateContinuation(
            debate_id=debate_id,
            idempotency_key=str(uuid.uuid4()),
            status="requested",
            user_id=current_user.id if current_user else None,
            target=debate.model_id,
            requested_at=sa.func.now(),
            retry_of_continuation_id=retry_of_continuation_id,
        )
        session.add(continuation_record)
        session.commit()

    # A process can crash after atomically committing preflight + scheduling,
    # but before registering the dispatch task.  That durable combination is
    # safe to resume: the reservation and scheduled Debate already exist, so
    # retry must continue at dispatch instead of rejecting the scheduled row.
    session.refresh(debate)
    resume_scheduled_dispatch = bool(
        continuation_record
        and continuation_record.status == "preflight_passed"
        and debate.status == "scheduled"
    )

    if not resume_scheduled_dispatch and debate.status not in {"perspectives_ready", "failed"}:
        exc = ValidationError(
            message="Debate is not paused or ready for continuation",
            code="debate.not_paused",
            status_code=400
        )
        if continuation_record:
            try:
                from services.continuations import transition_continuation_sync
                transition_continuation_sync(
                    session, continuation_record.id, ["requested"], "failed",
                    failure_code=getattr(exc, "code", "preflight_failed"),
                    failure_detail_safe=str(exc.detail) if hasattr(exc, "detail") else str(exc),
                )
            except Exception:
                logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
        raise exc

    from billing.service import get_active_plan, refund_hosted_credit, reserve_hosted_credit

    # A recovered scheduled continuation may already own a durable credit
    # reservation.  Preserve that identity for dispatch compensation without
    # reserving a second credit or rerunning preflight against a later state.
    credit_reserved = bool(
        resume_scheduled_dispatch
        and continuation_record
        and continuation_record.credit_reservation_id
    )

    if not resume_scheduled_dispatch:
        # 2. Preflight checks
        try:
            check_continue_preflight(debate, current_user, session)
        except Exception as exc:
            if continuation_record:
                try:
                    from services.continuations import transition_continuation_sync
                    transition_continuation_sync(
                        session, continuation_record.id, ["requested"], "failed",
                        failure_code=getattr(exc, "code", "preflight_failed"),
                        failure_detail_safe=str(exc.detail) if hasattr(exc, "detail") else str(exc),
                    )
                except Exception:
                    logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
            raise exc

        # 3. Credit reservation prior to state transition
        plan = get_active_plan(session, current_user.id)

        enabled_models = {m.id: m for m in list_enabled_models()}
        target_model_id = debate.model_id or get_default_model().id
        target_model_info = enabled_models.get(target_model_id)
        model_tier = "standard"
        if target_model_info:
            model_tier = getattr(target_model_info, "tier", "standard")

        is_sota_run = model_tier == "advanced" or debate.mode == "arena"

        if plan.is_default_free and is_sota_run:
            try:
                reservation_id = reserve_hosted_credit(
                    session,
                    current_user.id,
                    debate_id=debate_id,
                    run_attempt=max(int(getattr(debate, "run_attempt", 0) or 0), 1),
                    continuation_id=continuation_record.id if continuation_record else None,
                )
                credit_reserved = True
                if continuation_record and reservation_id:
                    continuation_record.credit_reservation_id = reservation_id
            except Exception as exc:
                if continuation_record:
                    try:
                        from services.continuations import transition_continuation_sync
                        transition_continuation_sync(
                            session, continuation_record.id, ["requested"], "failed",
                            failure_code=getattr(exc, "code", "hosted_credits.exhausted"),
                            failure_detail_safe=str(exc),
                        )
                    except Exception:
                        logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
                raise exc

        # Mark preflight passed (skip if already at preflight_passed from a resumed orphan)
        if continuation_record and continuation_record.status == "requested":
            from services.continuations import transition_continuation_sync
            transition_continuation_sync(
                session,
                continuation_record.id,
                ["requested"],
                "preflight_passed",
                commit=False,
            )

        # 4. Conditional atomic update
        stmt_upd = (
            sa.update(Debate)
            .where(Debate.id == debate_id)
            .where(Debate.status.in_(["perspectives_ready", "failed"]))
            .values(status="scheduled")
        )
        result = session.execute(stmt_upd)
        if result.rowcount == 0:
            # Roll back reservation, preflight transition and scheduling together.
            session.rollback()
            if continuation_record:
                try:
                    from services.continuations import transition_continuation_sync
                    transition_continuation_sync(
                        session,
                        continuation_record.id,
                        ["requested", "preflight_passed"],
                        "failed",
                        failure_code="debate.continue_conflict",
                        failure_detail_safe="This run is no longer waiting for continuation.",
                    )
                except Exception:
                    logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
            raise ValidationError(
                message="This run is no longer waiting for continuation.",
                code="debate.continue_conflict",
                status_code=409,
            )

        # Reservation + reservation identity + preflight transition + scheduling
        # become visible atomically.
        session.commit()

        # Refresh debate object
        session.refresh(debate)

    # 5. Dispatch task
    try:
        # Setup SSE channel
        channel_id = debate_channel_id(debate_id)
        await sse_backend.create_channel(channel_id)

        dispatch_args = (
            debate_id,
            debate.prompt,
            channel_id,
            debate.config or {},
            debate.model_id,
        )
        dispatch_kwargs = {
            "trace_id": None,
            "resume": True,
            "continuation_id": continuation_record.id if continuation_record else None,
        }

        if (settings.DEBATE_DISPATCH_MODE or "inline").lower() == "celery":
            # A Celery broker acknowledgement is the durable hand-off.  Enqueue
            # synchronously before publishing ``dispatched`` so a web-process
            # restart cannot leave a continuation that looks dispatched even
            # though no worker task exists.
            await dispatch_debate_run(*dispatch_args, **dispatch_kwargs)

            if continuation_record:
                from services.continuations import transition_continuation_sync

                try:
                    transition_continuation_sync(
                        session,
                        continuation_record.id,
                        ["preflight_passed"],
                        "dispatched",
                    )
                except Exception:
                    # The task is already durable.  Never refund or revert the
                    # scheduled Debate after broker acknowledgement: the worker
                    # can safely claim preflight_passed -> running, and execution
                    # fencing prevents duplicate ownership.
                    session.rollback()
                    logger.exception(
                        "Celery task enqueued but continuation %s could not be marked dispatched",
                        continuation_record.id,
                    )
        else:
            # Inline work starts only after Starlette has sent the response.
            # Keep the durable state at preflight_passed until the orchestrator
            # actually starts and transitions it to running.  A crash before
            # BackgroundTasks begins therefore remains resumable.
            background_tasks.add_task(
                dispatch_debate_run,
                *dispatch_args,
                **dispatch_kwargs,
            )
            
    except Exception as dispatch_exc:
        # P1 #5: All compensation must be in a single transaction.
        # transition_continuation_sync defaults to commit=True which would
        # commit refund + debate revert + continuation failure prematurely.
        if credit_reserved:
            refund_hosted_credit(
                session,
                current_user.id,
                reservation_id=getattr(continuation_record, "credit_reservation_id", None)
                if continuation_record
                else None,
                debate_id=debate_id,
            )
        
        stmt_revert = (
            sa.update(Debate)
            .where(Debate.id == debate_id)
            .values(status="perspectives_ready")
        )
        session.execute(stmt_revert)
        
        if continuation_record:
            try:
                from services.continuations import transition_continuation_sync
                transition_continuation_sync(
                    session, continuation_record.id, ["dispatched", "preflight_passed"], "failed",
                    failure_code="debate.dispatch_failed",
                    failure_detail_safe=str(dispatch_exc),
                    commit=False,
                )
            except Exception:
                logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
            
        session.commit()
        raise dispatch_exc

    from log_config import log_event
    log_event(
        "debate.continued",
        debate_id=debate_id,
        user_id=current_user.id if current_user else None,
        x_idempotency_key=x_idempotency_key,
    )
    from audit import record_audit
    record_audit(
        "debate_continue",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        meta={"x_idempotency_key": x_idempotency_key},
        session=session,
    )

    return ContinuationResponse(
        continuation_id=str(continuation_record.id),
        debate_id=debate_id,
        status="scheduled",
        debate_status=debate.status,
        idempotency_key=continuation_record.idempotency_key,
        created=True,
        retry_of_continuation_id=continuation_record.retry_of_continuation_id,
    )


@router.get("/debates/{debate_id}/continuations/{continuation_id}", response_model=ContinuationResponse)
async def get_debate_continuation(
    debate_id: str,
    continuation_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Load debate and verify read access
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    require_debate_access(debate, current_user, session)
    
    import uuid

    from models import DebateContinuation
    # Validate continuation_id is a valid UUID
    try:
        uuid.UUID(continuation_id)
    except ValueError as err:
        raise NotFoundError(message=f"Continuation {continuation_id} not found", code="continuation.not_found") from err

    continuation = session.get(DebateContinuation, continuation_id)
    if not continuation or str(continuation.debate_id) != debate_id:
        raise NotFoundError(message=f"Continuation {continuation_id} not found", code="continuation.not_found")
        
    return ContinuationResponse(
        continuation_id=str(continuation.id),
        debate_id=str(continuation.debate_id),
        status=continuation.status,
        debate_status=debate.status,
        idempotency_key=continuation.idempotency_key,
        created=False,
        retry_of_continuation_id=continuation.retry_of_continuation_id,
    )


@router.post("/debates/{debate_id}/continuations/resolve", response_model=ContinuationResponse)
async def resolve_continuation_by_key(
    debate_id: str,
    body: ContinuationResolveRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):

    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)

    stmt = select(DebateContinuation).where(
        DebateContinuation.debate_id == debate_id,
        DebateContinuation.idempotency_key == body.idempotency_key,
    )
    continuation = session.execute(stmt).scalars().first()
    if not continuation:
        raise NotFoundError(
            message="No continuation found for this idempotency key",
            code="continuation.not_found",
        )

    return ContinuationResponse(
        continuation_id=str(continuation.id),
        debate_id=str(continuation.debate_id),
        status=continuation.status,
        debate_status=debate.status,
        idempotency_key=continuation.idempotency_key,
        created=False,
        retry_of_continuation_id=continuation.retry_of_continuation_id,
    )


@router.post("/debates/{debate_id}/retry")
async def retry_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    body: Optional[RetryRequest] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    require_schema_current(session)
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)
    if debate.status in {"scheduled", "running"}:
        raise ValidationError(
            message="A run is already scheduled or active for this debate",
            code="debate.retry_conflict",
        )

    stage_key = body.stage_key if body else None
    from models import DebateAttempt, DebateStageCheckpoint

    if not stage_key:
        stmt = (
            select(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .where(DebateStageCheckpoint.status == "failed")
            .order_by(DebateStageCheckpoint.started_at.desc())
        )
        failed_checkpoint = session.execute(stmt).scalars().first()
        if failed_checkpoint:
            stage_key = failed_checkpoint.stage_key
        else:
            stmt_last = (
                select(DebateStageCheckpoint)
                .where(DebateStageCheckpoint.debate_id == debate_id)
                .order_by(DebateStageCheckpoint.started_at.desc())
            )
            last_checkpoint = session.execute(stmt_last).scalars().first()
            if last_checkpoint:
                stage_key = last_checkpoint.stage_key

    # The endpoint prepares attempt N; lease acquisition is the sole writer of
    # Debate.run_attempt and will atomically advance it to that same N.
    next_attempt = (debate.run_attempt or 0) + 1
    reservation_id: str | None = None
    billing_reserved = False
    try:
        reservation_id = _reserve_retry_billing(
            session, current_user, debate, next_attempt=next_attempt
        )
        billing_reserved = True

        if stage_key:
            from orchestration.stage_graph import get_stages_to_invalidate

            stages_to_clear = get_stages_to_invalidate(stage_key)
            session.execute(
                sa.update(DebateStageCheckpoint)
                .where(DebateStageCheckpoint.debate_id == debate_id)
                .where(DebateStageCheckpoint.stage_key.in_(stages_to_clear))
                .values(status="invalidated")
            )

        debate.status = "scheduled"
        debate.updated_at = utcnow()
        debate.credit_reservation_id = reservation_id
        session.add(debate)
        session.add(
            DebateAttempt(
                debate_id=debate_id,
                attempt_number=next_attempt,
                status="queued",
                model_id=debate.model_id,
                created_at=utcnow(),
            )
        )

        channel_id = debate_channel_id(debate_id)
        await sse_backend.create_channel(channel_id)
        # Monthly usage, hosted-credit reservation, retry state and attempt row
        # become durable together. Hourly slot was committed by reserve_run_slot.
        session.commit()
    except Exception:
        session.rollback()
        if billing_reserved:
            from usage_limits import refund_run_slot

            refund_run_slot(session, current_user.id)
        raise

    background_tasks.add_task(
        dispatch_debate_run,
        debate_id,
        debate.prompt,
        channel_id,
        debate.config or {},
        debate.model_id,
        trace_id=None,
        resume=True,
    )

    from audit import record_audit
    from log_config import log_event

    log_event(
        "debate.retried",
        debate_id=debate_id,
        user_id=current_user.id,
        stage_key=stage_key,
        attempt_number=next_attempt,
    )
    record_audit(
        "debate_retry",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        meta={"stage_key": stage_key, "attempt_number": next_attempt},
        session=session,
    )
    session.commit()

    return {
        "id": debate_id,
        "status": "scheduled",
        "retried_stage": stage_key,
        "attempt_number": next_attempt,
    }


@router.post("/debates/{debate_id}/retry-agent")
async def retry_agent(
    debate_id: str,
    body: RetryAgentRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)
    if debate.status in {"scheduled", "running"}:
        raise ValidationError(
            message="Agent retry is unavailable while the debate is running",
            code="debate.retry_conflict",
        )

    target_persona = body.persona
    agent_config_dict = None
    agents_list = debate.config.get("agents", []) if debate.config else []
    for agent in agents_list:
        if agent.get("name") == target_persona:
            agent_config_dict = agent
            break
    if not agent_config_dict:
        panel_seats = debate.panel_config.get("seats", []) if debate.panel_config else []
        for seat in panel_seats:
            if seat.get("name") == target_persona or seat.get("display_name") == target_persona:
                agent_config_dict = {
                    "name": seat.get("name") or seat.get("display_name"),
                    "model": seat.get("model"),
                    "provider": seat.get("provider") or seat.get("provider_key"),
                    "persona": seat.get("persona_tagline") or seat.get("role_profile"),
                }
                break
    if not agent_config_dict:
        raise ValidationError(
            message=f"Agent '{target_persona}' config not found in debate",
            code="agent.not_found",
        )

    agent_provider = agent_config_dict.get("provider", "unknown")
    from schemas import AgentConfig

    agent_config = AgentConfig(
        name=agent_config_dict.get("name", target_persona),
        persona=agent_config_dict.get("persona", ""),
        model=agent_config_dict.get("model"),
        tools=agent_config_dict.get("tools"),
    )

    from models import DebateAttempt

    next_attempt = (debate.run_attempt or 0) + 1
    reservation_id: str | None = None
    billing_committed = False
    try:
        reservation_id = _reserve_retry_billing(
            session, current_user, debate, next_attempt=next_attempt
        )
        debate.run_attempt = next_attempt
        attempt = DebateAttempt(
            debate_id=debate_id,
            attempt_number=next_attempt,
            status="running",
            model_id=debate.model_id,
            created_at=utcnow(),
        )
        session.add(debate)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        billing_committed = True
    except Exception:
        session.rollback()
        from usage_limits import refund_run_slot

        refund_run_slot(session, current_user.id)
        raise

    await sse_backend.publish(
        f"debate:{debate_id}",
        {
            "type": "notice",
            "level": "info",
            "debate_id": debate_id,
            "message": f"Retrying agent '{target_persona}'...",
        },
    )

    from agents import produce_candidate

    try:
        candidate_payload, _candidate_usage = await produce_candidate(
            debate.prompt,
            agent_config,
            model_id=debate.model_id,
            debate_id=debate.id,
        )

        import hashlib

        persona_hash = hashlib.sha256(target_persona.encode("utf-8")).hexdigest()[:12]
        response_id = f"agent-retry:{debate_id}:a{next_attempt}:{persona_hash}"
        existing_msg = session.exec(
            select(Message).where(
                Message.debate_id == debate_id,
                Message.attempt_id == attempt.id,
                Message.response_id == response_id,
            )
        ).first()
        if existing_msg is None:
            session.add(
                Message(
                    debate_id=debate_id,
                    attempt_id=attempt.id,
                    response_id=response_id,
                    round_index=1,
                    role="candidate",
                    persona=target_persona,
                    content=candidate_payload.get("text", ""),
                    meta={
                        **{
                            key: value
                            for key, value in candidate_payload.items()
                            if key not in {"persona", "text"}
                        },
                        "retry_generation": next_attempt,
                    },
                )
            )

        import copy

        final_meta = copy.deepcopy(debate.final_meta or {})
        model_warnings = final_meta.get("model_warnings", [])
        final_meta["model_warnings"] = [
            warning
            for warning in model_warnings
            if warning.get("display_name") != target_persona
            and warning.get("persona_name") != target_persona
        ]
        models_list = final_meta.get("models", [])
        for model_info in models_list:
            if model_info.get("display_name") == target_persona:
                model_info["success"] = True
        final_meta["successful_count"] = sum(
            1 for model_info in models_list if model_info.get("success") is not False
        )
        final_meta["models"] = models_list
        debate.final_meta = final_meta
        attempt.status = "completed"
        session.add(debate)
        session.add(attempt)

        if reservation_id:
            from billing.service import consume_hosted_credit

            consume_hosted_credit(
                session,
                current_user.id,
                reservation_id=reservation_id,
                debate_id=debate_id,
            )
        session.commit()

        await sse_backend.publish(
            f"debate:{debate_id}",
            {
                "type": "arena_response",
                "debate_id": debate_id,
                "model_id": agent_config.model,
                "display_name": target_persona,
                "provider": agent_provider,
                "content": candidate_payload.get("text", ""),
                "success": True,
                "response_id": response_id,
                "run_attempt": next_attempt,
            },
        )
        return {
            "success": True,
            "message": f"Agent '{target_persona}' successfully retried.",
            "content": candidate_payload.get("text", ""),
            "attempt_number": next_attempt,
        }
    except Exception as exc:
        logger.exception("Failed to retry agent %s", target_persona)
        session.rollback()
        if billing_committed:
            attempt_db = session.get(DebateAttempt, attempt.id)
            if attempt_db:
                attempt_db.status = "failed"
                session.add(attempt_db)
            _refund_committed_retry_billing(
                session,
                current_user,
                debate,
                reservation_id=reservation_id,
            )
        await sse_backend.publish(
            f"debate:{debate_id}",
            {
                "type": "notice",
                "level": "error",
                "debate_id": debate_id,
                "message": f"Retry for agent '{target_persona}' failed.",
            },
        )
        raise HTTPException(
            status_code=500, detail="Agent retry failed. Please try again later."
        ) from exc
