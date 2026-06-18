import asyncio
import logging
import uuid
from typing import Optional

import sqlalchemy as sa
from auth import get_current_user, get_optional_user
from channels import debate_channel_id
from config import settings
from debate_dispatch import dispatch_debate_run
from deps import get_session, get_sse_backend
from exceptions import (
    NotFoundError,
    ValidationError,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from models import Debate, DebateContinuation, Message, User, utcnow
from parliament.model_registry import list_enabled_models, get_default_model
from parliament.router_v2 import RouteContext, choose_model
from pydantic import BaseModel
from schemas import (
    ContinuationResponse,
    ContinuationRequest,
    default_debate_config,
)
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend

from routes.common import (
    require_debate_access,
    require_debate_mutation_access,
    require_schema_current,
    track_metric,
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
    from parliament.model_registry import list_enabled_models, get_default_model
    from parliament.provider_health import get_health_state
    from datetime import datetime, timezone

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


@router.post("/debates/{debate_id}/start")
async def start_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
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
    log_event(
        "debate.started_manually",
        debate_id=debate_id,
        user_id=current_user.id if current_user else None,
        model_id=debate.model_id,
    )

    from audit import record_audit
    record_audit(
        "debate_manual_start",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
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
            if continuation_record.status in {"requested", "preflight_passed", "dispatched", "running", "completed", "paused"}:
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
                if continuation_record and continuation_record.status in {"requested", "preflight_passed", "dispatched", "running", "completed", "paused"}:
                    return ContinuationResponse(
                        continuation_id=str(continuation_record.id),
                        debate_id=debate_id,
                        status=continuation_record.status,
                        debate_status=debate.status,
                        idempotency_key=continuation_record.idempotency_key,
                        created=False,
                        retry_of_continuation_id=continuation_record.retry_of_continuation_id,
                    )
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

    if debate.status not in {"perspectives_ready", "failed"}:
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

    # 3. Credit Reservation prior to state transition
    from billing.service import get_active_plan, reserve_hosted_credit, refund_hosted_credit
    plan = get_active_plan(session, current_user.id)
    
    from parliament.model_registry import list_enabled_models, get_default_model
    enabled_models = {m.id: m for m in list_enabled_models()}
    target_model_id = debate.model_id or get_default_model().id
    target_model_info = enabled_models.get(target_model_id)
    model_tier = "standard"
    if target_model_info:
        model_tier = getattr(target_model_info, "tier", "standard")
        
    is_sota_run = (model_tier == "advanced" or debate.mode == "arena")
    credit_reserved = False
    
    if plan.is_default_free and is_sota_run:
        try:
            reserve_hosted_credit(session, current_user.id)
            credit_reserved = True
            if continuation_record:
                continuation_record.credit_reservation_id = "hosted_credit"
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

    # Mark preflight passed
    if continuation_record:
        from services.continuations import transition_continuation_sync
        transition_continuation_sync(
            session, continuation_record.id, ["requested"], "preflight_passed"
        )

    # 4. Conditional atomic update
    stmt_upd = (
        sa.update(Debate)
        .where(Debate.id == debate_id)
        .where(Debate.status.in_(["perspectives_ready", "failed"]))
        .values(status="scheduled")
    )
    result = session.execute(stmt_upd)
    session.commit()

    if result.rowcount == 0:
        if credit_reserved:
            refund_hosted_credit(session, current_user.id)
            session.commit()
        if continuation_record:
            try:
                from services.continuations import transition_continuation_sync
                transition_continuation_sync(
                    session, continuation_record.id, ["preflight_passed"], "failed",
                    failure_code="debate.continue_conflict",
                    failure_detail_safe="This run is no longer waiting for continuation.",
                )
            except Exception:
                logger.warning("Failed to transition continuation %s to failed", continuation_record.id)
        raise ValidationError(
            message="This run is no longer waiting for continuation.",
            code="debate.continue_conflict",
            status_code=409
        )

    # Refresh debate object
    session.refresh(debate)

    # 5. Dispatch task
    try:
        # Setup SSE channel
        channel_id = debate_channel_id(debate_id)
        await sse_backend.create_channel(channel_id)

        # Dispatch task (resume = True)
        background_tasks.add_task(
            dispatch_debate_run,
            debate_id,
            debate.prompt,
            channel_id,
            debate.config or {},
            debate.model_id,
            trace_id=None,
            resume=True,
            continuation_id=continuation_record.id if continuation_record else None,
        )

        # Mark continuation as dispatched
        if continuation_record:
            from services.continuations import transition_continuation_sync
            transition_continuation_sync(
                session, continuation_record.id, ["preflight_passed"], "dispatched"
            )
            
    except Exception as dispatch_exc:
        if credit_reserved:
            refund_hosted_credit(session, current_user.id)
        
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
    
    from models import DebateContinuation
    import uuid
    # Validate continuation_id is a valid UUID
    try:
        uuid.UUID(continuation_id)
    except ValueError:
        raise NotFoundError(message=f"Continuation {continuation_id} not found", code="continuation.not_found")

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
    # Load debate and verify mutation access
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)

    # 1. Determine target stage(s) to clear
    stage_key = body.stage_key if body else None
    
    from models import DebateStageCheckpoint, Score, Vote
    if not stage_key:
        # If no stage key specified, look for any failed stage
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
            # Default to clearing last executed stage checkpoint if any exist
            stmt_last = (
                select(DebateStageCheckpoint)
                .where(DebateStageCheckpoint.debate_id == debate_id)
                .order_by(DebateStageCheckpoint.started_at.desc())
            )
            last_checkpoint = session.execute(stmt_last).scalars().first()
            if last_checkpoint:
                stage_key = last_checkpoint.stage_key

    # If we still have a stage_key, invalidate downstream checkpoints (non-destructive)
    if stage_key:
        from orchestration.stage_graph import get_stages_to_invalidate
        
        stages_to_clear = get_stages_to_invalidate(stage_key)
        
        # Invalidate downstream checkpoints instead of deleting evidence
        # Prior attempt evidence remains immutable and inspectable
        stmt_invalidate = (
            sa.update(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .where(DebateStageCheckpoint.stage_key.in_(stages_to_clear))
            .values(status="invalidated")
        )
        session.execute(stmt_invalidate)

        session.commit()

    # 2. Reset debate status to scheduled to trigger execution (force resume = True)
    debate.status = "scheduled"
    debate.updated_at = sa.func.now()
    debate.run_attempt = (debate.run_attempt or 0) + 1
    session.add(debate)

    # FH125 G-7: Create DebateAttempt record for non-destructive retry
    from models import DebateAttempt
    attempt = DebateAttempt(
        debate_id=debate_id,
        attempt_number=debate.run_attempt,
        status="queued",
        model_id=debate.model_id,
        created_at=utcnow(),
    )
    session.add(attempt)
    session.commit()

    # Setup SSE channel
    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)

    # Dispatch task
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

    from log_config import log_event
    log_event(
        "debate.retried",
        debate_id=debate_id,
        user_id=current_user.id if current_user else None,
        stage_key=stage_key,
    )
    from audit import record_audit
    record_audit(
        "debate_retry",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        meta={"stage_key": stage_key},
        session=session,
    )

    return {"id": debate_id, "status": "scheduled", "retried_stage": stage_key}


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
    target_persona = body.persona

    # FH125 G-7: Create new DebateAttempt for retry isolation
    from models import DebateAttempt
    debate.run_attempt = (debate.run_attempt or 0) + 1
    attempt = DebateAttempt(
        debate_id=debate_id,
        attempt_number=debate.run_attempt,
        status="running",
        model_id=debate.model_id,
        created_at=utcnow(),
    )
    session.add(attempt)
    session.commit()

    agent_config_dict = None
    agents_list = debate.config.get("agents", []) if debate.config else []
    for ag in agents_list:
        if ag.get("name") == target_persona:
            agent_config_dict = ag
            break
            
    if not agent_config_dict:
        panel_seats = debate.panel_config.get("seats", []) if debate.panel_config else []
        for seat in panel_seats:
            if seat.get("name") == target_persona:
                agent_config_dict = {
                    "name": seat.get("name"),
                    "model": seat.get("model"),
                    "provider": seat.get("provider"),
                    "persona": seat.get("persona_tagline"),
                }
                break

    if not agent_config_dict:
        raise ValidationError(message=f"Agent '{target_persona}' config not found in debate", code="agent.not_found")

    # Extract provider before constructing AgentConfig (AgentConfig schema has no provider field)
    agent_provider = agent_config_dict.get("provider", "unknown")

    from schemas import AgentConfig
    # Only pass fields that AgentConfig accepts
    agent_config = AgentConfig(
        name=agent_config_dict.get("name", target_persona),
        persona=agent_config_dict.get("persona", ""),
        model=agent_config_dict.get("model"),
        tools=agent_config_dict.get("tools"),
    )

    await sse_backend.publish(
        f"debate:{debate_id}",
        {
            "type": "notice",
            "level": "info",
            "debate_id": debate_id,
            "message": f"Retrying agent '{target_persona}'...",
        }
    )

    from agents import produce_candidate
    try:
        candidate_payload, candidate_usage = await produce_candidate(
            debate.prompt,
            agent_config,
            model_id=debate.model_id,
            debate_id=debate.id,
        )
        
        stmt = select(Message).where(
            Message.debate_id == debate_id,
            Message.round_index == 1,
            Message.persona == target_persona,
            Message.role == "candidate"
        )
        existing_msg = session.exec(stmt).first()
        if existing_msg:
            existing_msg.content = candidate_payload.get("text", "")
            existing_msg.meta = {k: v for k, v in candidate_payload.items() if k not in {"persona", "text"}}
            session.add(existing_msg)
        else:
            new_msg = Message(
                debate_id=debate_id,
                round_index=1,
                role="candidate",
                persona=target_persona,
                content=candidate_payload.get("text", ""),
                meta={k: v for k, v in candidate_payload.items() if k not in {"persona", "text"}},
            )
            session.add(new_msg)

        try:
            from billing.service import increment_debate_usage as _inc_usage
            _inc_usage(session, current_user.id)
        except Exception as usage_err:
            logging.getLogger("fastapi").warning(f"Failed to increment usage: {usage_err}")

        import copy
        final_meta = copy.deepcopy(debate.final_meta or {})
        model_warnings = final_meta.get("model_warnings", [])
        new_warnings = [w for w in model_warnings if w.get("display_name") != target_persona and w.get("persona_name") != target_persona]
        final_meta["model_warnings"] = new_warnings
        
        models_list = final_meta.get("models", [])
        for m_info in models_list:
            if m_info.get("display_name") == target_persona:
                m_info["success"] = True
                
        final_meta["successful_count"] = sum(1 for m in models_list if m.get("success") != False)
        final_meta["models"] = models_list
        debate.final_meta = final_meta
        session.add(debate)
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
            }
        )

        return {
            "success": True,
            "message": f"Agent '{target_persona}' successfully retried.",
            "content": candidate_payload.get("text", ""),
        }
    except Exception as exc:
        logging.getLogger("fastapi").exception(f"Failed to retry agent {target_persona}: {exc}")
        await sse_backend.publish(
            f"debate:{debate_id}",
            {
                "type": "notice",
                "level": "error",
                "debate_id": debate_id,
                "message": f"Retry for agent '{target_persona}' failed.",
            }
        )
        raise HTTPException(status_code=500, detail="Agent retry failed. Please try again later.")
