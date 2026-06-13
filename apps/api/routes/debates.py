import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from audit import record_audit
from auth import get_current_user, get_optional_user
from billing.service import check_export_quota, increment_debate_usage, increment_export_usage
from channels import debate_channel_id
from config import settings
from debate_dispatch import dispatch_debate_run
from deps import get_session, get_sse_backend
from exceptions import (
    AppError,
    NotFoundError,
    PermissionError,
    ProviderCircuitOpenError,
    RateLimitError,
    ValidationError,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from integrations.langfuse import start_debate_trace
from models import Debate, Message, PairwiseVote, Score, Team, User
from parliament.model_registry import list_enabled_models
from parliament.providers import PROVIDERS
from parliament.roles import ROLE_PROFILES
from parliament.router_v2 import RouteContext, choose_model
from parliament.schemas import TimelineEvent
from parliament.timeline import build_debate_timeline
from pydantic import BaseModel
from ratelimit import increment_ip_bucket, record_429
from schemas import (
    DebateConfig,
    DebateCreate,
    PanelConfig,
    default_debate_config,
    default_panel_config,
)
from sqlalchemy import func
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend
from usage_limits import reserve_run_slot

from routes.common import (
    champion_for_debate,
    is_debate_owner,
    is_debate_public,
    members_from_config,
    require_debate_access,
    require_debate_mutation_access,
    require_debate_owner,
    serialize_rating_persona,
    track_metric,
    user_is_team_member,
)
from serializers import (
    serialize_debate_private,
    serialize_debate_public,
    serialize_events_public,
)

logger = logging.getLogger(__name__)



router = APIRouter(tags=["debates"])


class DebateUpdate(BaseModel):
    team_id: Optional[str] = None


def _champion_for_debate(session: Session, debate_id: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    return champion_for_debate(session, debate_id)


def _members_from_config(config: DebateConfig, panel: PanelConfig | None = None) -> list[dict[str, str]]:
    return members_from_config(config, panel)


@router.get("/config/default")
async def get_default_config():
    return default_debate_config()


@router.get("/leaderboard")
async def get_leaderboard(
    response: Response,
    category: Optional[str] = Query(default=None),
    min_matches: int = Query(0, ge=0, le=1000),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    from models import RatingPersona

    stmt = select(RatingPersona).order_by(RatingPersona.elo.desc())
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    if min_matches:
        stmt = stmt.where(RatingPersona.n_matches >= min_matches)
    stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()
    payload = {"items": [serialize_rating_persona(row) for row in rows]}
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/leaderboard/persona/{persona}")
async def get_leaderboard_persona(
    response: Response,
    persona: str,
    category: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    from models import RatingPersona

    stmt = select(RatingPersona).where(RatingPersona.persona == persona)
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    row = session.exec(stmt).first()
    if not row:
        raise NotFoundError(message="Persona not found", code="leaderboard.persona_not_found")
    payload = serialize_rating_persona(row)
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/debates/{debate_id}/members")
async def get_debate_members(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    panel = None
    if debate.panel_config:
        try:
            panel = PanelConfig.model_validate(debate.panel_config)
        except Exception:
            panel = None
    return {"members": _members_from_config(config, panel)}

@router.get("/debates/{debate_id}/timeline", response_model=list[TimelineEvent])
async def get_debate_timeline(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    import time
    start_time = time.time()
    debate = session.get(Debate, debate_id)
    debate = require_debate_access(debate, current_user, session)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    
    # Return partial timeline for running debates instead of erroring
    timeline = build_debate_timeline(session, debate)
    
    elapsed_ms = (time.time() - start_time) * 1000
    # Patchset 112: Track timeline fetch performance
    if elapsed_ms > 500:
        logger.warning(f"timeline_fetch_slow: debate_id={debate_id} elapsed_ms={elapsed_ms:.1f} events={len(timeline)}")
        track_metric("timeline.fetch.slow")
    else:
        track_metric("timeline.fetch.ok")

    return timeline


@router.post("/debates")
async def create_debate(
    body: DebateCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # 1. Account Active Check
    from fastapi import HTTPException
    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_disabled",
                "message": "Your account has been disabled. Please contact support.",
            }
        )

    # 2. IP Rate Limit Check
    ip = request.client.host if request.client else "anonymous"
    user_id = current_user.id if current_user else None
    allowed, retry_after = increment_ip_bucket(ip, settings.RL_DEBATE_CREATE_WINDOW, settings.RL_DEBATE_CREATE_MAX_CALLS, user_id=user_id)

    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)

    # 3. Daily Token quota check
    from usage_limits import QuotaExceededError, check_quota
    estimated_tokens = 5000  # Average debate uses ~5k tokens
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

    # 4. Hourly / Monthly Plan run limits check
    try:
        reserve_run_slot(session, current_user.id)
        increment_debate_usage(session, current_user.id)
    except RateLimitError as exc:
        payload = {
            "code": "rate_limit",
            "reason": exc.code,
            "detail": exc.detail,
            "reset_at": exc.reset_at,
        }
        record_audit(
            "rate_limit_block",
            user_id=current_user.id,
            target_type="debate",
            target_id=None,
            meta=payload,
            session=session,
        )
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.quota_exceeded", details=payload) from exc

    try:
        # Patchset 54.0: Check feature flag for conversation mode
        if body.mode == "conversation":
            if not settings.ENABLE_CONVERSATION_MODE:
                raise ValidationError(
                    message="Conversation mode is not available",
                    code="feature.disabled",
                    hint="This feature is currently disabled. Please contact support."
                )
            # Patchset 50.3: Check beta access for conversation mode
            from beta_access import require_beta_access
            require_beta_access(current_user, "conversation mode")

        config = body.config or default_debate_config()
        enabled_models = {m.id: m for m in list_enabled_models()}
        if not enabled_models:
            raise ProviderCircuitOpenError(
                message="No models available; configure provider keys.", 
                code="models.unavailable",
                hint="Please contact the administrator to configure model providers."
            )
        
        # Validate requested model if provided
        if body.model_id and body.model_id not in enabled_models:
            raise ValidationError(
                message="Invalid or unavailable model_id", 
                code="debate.invalid_model",
                hint="Please select a different model from the list."
            )
        
        # Patchset 49.2: Enforce model tier limits
        from billing.service import get_active_plan, reserve_hosted_credit
        plan = get_active_plan(session, current_user.id)
        
        # Check the model's tier
        from parliament.model_registry import get_default_model
        target_model_id = body.model_id or get_default_model().id
        target_model_info = enabled_models.get(target_model_id)
        model_tier = "standard"
        if target_model_info:
            model_tier = getattr(target_model_info, "tier", "standard")

        # Phase 8: Hosted Credits check for Free plan users - only for advanced/SOTA models
        is_sota_run = (model_tier == "advanced" or body.mode == "arena")
        has_hosted_credits = False
        if plan.is_default_free and is_sota_run:
            try:
                reserve_hosted_credit(session, current_user.id)
                has_hosted_credits = True
            except ValidationError as exc:
                if exc.code == "hosted_credits.exhausted" and body.model_id is not None:
                    raise ValidationError(
                        message=f"Model '{target_model_info.display_name if target_model_info else target_model_id}' is not available on your plan.",
                        code="debate.model_tier_restricted",
                        hint="Please upgrade to Pro to use advanced models."
                    ) from exc
                raise exc

        allowed_tiers = plan.limits.get("allowed_model_tiers")

        # If allowed_tiers is not set, default to ["standard"] for Free plans (is_default_free=True)
        # and ["standard", "advanced"] for others, unless explicitly configured.
        if allowed_tiers is None:
            if plan.is_default_free:
                allowed_tiers = ["standard"]
            else:
                allowed_tiers = ["standard", "advanced"]

        # Free tier user who successfully reserved a hosted credit is permitted to run advanced models
        if plan.is_default_free and has_hosted_credits:
            allowed_tiers = list(allowed_tiers)
            if "advanced" not in allowed_tiers:
                allowed_tiers.append("advanced")
                
        if model_tier not in allowed_tiers:
             raise ValidationError(
                message=f"Model '{target_model_info.display_name if target_model_info else target_model_id}' is not available on your plan.",
                code="debate.model_tier_restricted",
                hint="Please upgrade to Pro to use advanced models."
            )
    except Exception as exc:
        # Refund run slot & debate usage
        try:
            from usage_limits import _get_or_reset_counter
            counter = _get_or_reset_counter(session, current_user.id, "hour")
            if counter.runs_used > 0:
                counter.runs_used -= 1
                session.add(counter)
            from billing.service import get_or_create_usage
            usage = get_or_create_usage(session, current_user.id)
            if usage.debates_created > 0:
                usage.debates_created -= 1
                session.add(usage)
            session.commit()
        except Exception as refund_err:
            logger.error(f"Failed to refund quotas during creation failure: {refund_err}")
        raise exc

    panel_config = body.panel_config or default_panel_config()
    try:
        panel = PanelConfig.model_validate(panel_config)
    except Exception as exc:  # pragma: no cover - validation
        raise ValidationError(message="Invalid panel_config payload", code="debate.invalid_panel_config") from exc
    for seat in panel.seats:
        if seat.provider_key not in PROVIDERS:
            raise ValidationError(message=f"Unknown provider_key '{seat.provider_key}'", code="debate.invalid_provider")
        if seat.role_profile not in ROLE_PROFILES:
            raise ValidationError(message=f"Unknown role_profile '{seat.role_profile}'", code="debate.invalid_role")

    # Routing decision
    route_ctx = RouteContext(
        user_id=current_user.id,
        requested_model=body.model_id,
        routing_policy=body.routing_policy,
        debate_type="standard",
        priority="normal",
    )
    best_model_id, candidates = choose_model(route_ctx)
    
    # Structured logging for routing decisions
    logger.info(
        "Routing decision made",
        extra={
            "selected_model": best_model_id,
            "routing_policy": body.routing_policy or "router-smart",
            "explicit_override": body.model_id is not None,
            "candidate_count": len(candidates),
            "top_candidates": [
                {"model": c.model, "score": round(c.total_score, 3)}
                for c in candidates[:3]
            ] if candidates else [],
            "user_id": current_user.id,
        },
    )
    
    # Track routing metrics
    from routes.common import track_metric
    track_metric(f"routing.policy.{body.routing_policy or 'router-smart'}")
    track_metric(f"routing.model.{best_model_id}")
    if body.model_id:
        track_metric("routing.explicit_override")
    
    debate_id = str(uuid.uuid4())

    # Patchset 41.0: Start Langfuse trace
    trace_id = start_debate_trace(
        debate_id=debate_id,
        user_id=str(current_user.id),
        routed_model=best_model_id,
        routing_policy=body.routing_policy,
    )

    config_payload = config.model_dump()
    # Store locale in config so the engine can instruct LLMs to respond in user's language
    if body.locale:
        config_payload["locale"] = body.locale
    if body.mode == "compare":
        if not body.compare_models or len(body.compare_models) < 2:
            raise ValidationError(message="Compare mode requires at least 2 models", code="debate.invalid_compare_models")
        config_payload["compare_models"] = body.compare_models

    debate = Debate(
        id=debate_id,
        prompt=body.prompt,
        status="queued",
        config=config_payload,
        user_id=current_user.id,
        model_id=best_model_id,
        routed_model=best_model_id,
        routing_policy=body.routing_policy,
        gateway_policy=body.gateway_policy or "auto",
        routing_meta={
            "candidates": [c.model_dump() for c in candidates],
            "requested_model": body.model_id,
        },
        panel_config=panel.model_dump(),
        engine_version=panel.engine_version,
        mode=body.mode or "arena",
    )
    session.add(debate)
    session.commit()

    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)

    if not settings.DISABLE_AUTORUN:
        background_tasks.add_task(
            dispatch_debate_run,
            debate_id,
            body.prompt,
            channel_id,
            config_payload,
            best_model_id,
            trace_id=trace_id,
        )
    
    from log_config import log_event
    log_event(
        "debate.created",
        debate_id=debate_id,
        user_id=current_user.id,
        model_id=best_model_id,
        autorun=not settings.DISABLE_AUTORUN,
    )

    record_audit(
        "debate_created",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        meta={"prompt": body.prompt},
        session=session,
    )
    track_metric("debates_created")
    # Patchset 112: Track mode usage metrics
    mode = body.mode or "conversation"
    # Replaced legacy mode.{mode}.started with consistent mode.debate.started 
    # and tracking the specific mode as a tag or sub-metric if needed, but for now just:
    track_metric(f"mode.debate.{mode}.started")
    return {"id": debate_id}


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

    record_audit(
        "debate_manual_start",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        session=session,
    )
    return {"id": debate_id, "status": "scheduled"}


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


from fastapi import Header, HTTPException

@router.post("/debates/{debate_id}/continue")
async def continue_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Load debate and verify mutation access
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message=f"Debate {debate_id} not found", code="debate.not_found")
    debate = require_debate_mutation_access(debate, current_user, session)

    # 1. Idempotency Check
    continuation_record = None
    if x_idempotency_key:
        from models import DebateContinuation
        stmt_chk = select(DebateContinuation).where(
            DebateContinuation.debate_id == debate_id,
            DebateContinuation.idempotency_key == x_idempotency_key
        )
        continuation_record = session.execute(stmt_chk).scalars().first()
        if continuation_record:
            if continuation_record.status in {"requested", "dispatched", "completed"}:
                # Act as a no-op
                return {"id": debate_id, "status": debate.status}
            # If status is failed, allow retry by updating status to requested
            continuation_record.status = "requested"
            continuation_record.updated_at = sa.func.now()
            session.add(continuation_record)
            session.commit()
        else:
            continuation_record = DebateContinuation(
                debate_id=debate_id,
                idempotency_key=x_idempotency_key,
                status="requested"
            )
            session.add(continuation_record)
            try:
                session.commit()
            except sa.exc.IntegrityError:
                session.rollback()
                continuation_record = session.execute(stmt_chk).scalars().first()
                if continuation_record and continuation_record.status in {"requested", "dispatched", "completed"}:
                    return {"id": debate_id, "status": debate.status}

    # 2. Preflight checks
    check_continue_preflight(debate, current_user, session)

    # 3. Conditional atomic update
    stmt_upd = (
        sa.update(Debate)
        .where(Debate.id == debate_id)
        .where(Debate.status.in_(["perspectives_ready", "failed"]))
        .values(status="scheduled")
    )
    result = session.execute(stmt_upd)
    session.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=409,
            detail="Conflict: Debate run is already in progress, completed, or cannot be continued."
        )

    # Refresh debate object
    session.refresh(debate)

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
        True,
    )

    # 4. Mark continuation as dispatched
    if continuation_record:
        continuation_record.status = "dispatched"
        continuation_record.updated_at = sa.func.now()
        session.add(continuation_record)
        session.commit()

    from log_config import log_event
    log_event(
        "debate.continued",
        debate_id=debate_id,
        user_id=current_user.id if current_user else None,
        x_idempotency_key=x_idempotency_key,
    )
    record_audit(
        "debate_continue",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        meta={"x_idempotency_key": x_idempotency_key},
        session=session,
    )

    return {"id": debate_id, "status": "scheduled"}



from pydantic import BaseModel

class DebateListResponse(BaseModel):
    items: list[Debate]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("/debates", response_model=DebateListResponse)
async def list_debates(
    status: Optional[str] = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(default=None, max_length=200),
):
    filters = []
    if current_user.role != "admin":
        from routes.common import user_team_ids

        team_ids = user_team_ids(session, current_user.id)
        if team_ids:
            filters.append((Debate.user_id == current_user.id) | (Debate.team_id.in_(team_ids)))
        else:
            filters.append(Debate.user_id == current_user.id)
    elif status == "all":
        status = None
    if status:
        filters.append(Debate.status == status)
    if isinstance(q, str):
        query_text = q.strip()
        if query_text:
            search_term = f"%{query_text.lower()}%"
            filters.append(
                sa.or_(
                    sa.func.lower(Debate.prompt).contains(query_text.lower()),
                    sa.func.lower(Debate.id).contains(query_text.lower()),
                    sa.func.lower(Debate.mode).contains(query_text.lower()),
                    sa.func.lower(Debate.status).contains(query_text.lower()),
                )
            )

    # Patchset 59.5: Eager load user and team to avoid N+1 queries during serialization
    from sqlalchemy.orm import selectinload
    base_query = select(Debate).options(
        selectinload(Debate.user),
        # selectinload(Debate.team) # Team is currently just an ID on Debate, but if we had a relationship:
        # selectinload(Debate.team_rel) 
    )
    if filters:
        base_query = base_query.where(*filters)

    # Caching for total count
    # Patchset 112: Use shared Redis connection pool
    total = None
    cache_key = None
    redis_client = None
    if settings.REDIS_URL:
        try:
            from redis_pool import get_sync_redis_client
            redis_client = get_sync_redis_client()
            if redis_client:
                # Cache Key Pattern: count:debates:<hash(user_id + status + q)>
                # TTL: 30 seconds
                key_parts = [str(current_user.id), str(status), str(q)]
                cache_key = f"count:debates:{hash(''.join(key_parts))}"
                cached = redis_client.get(cache_key)
                if cached:
                    total = int(cached)
        except Exception:
            pass

    if total is None:
        count_stmt = select(func.count(Debate.id))
        for f in filters:
            count_stmt = count_stmt.where(f)
        total_result = session.exec(count_stmt).one()
        if isinstance(total_result, tuple):
            total_result = total_result[0]
        total = int(total_result or 0)
        
        if redis_client and cache_key:
            try:
                redis_client.setex(cache_key, 30, total)  # Cache for 30 seconds
            except Exception:
                pass

    items_stmt = base_query.order_by(sa.desc(Debate.created_at)).offset(offset).limit(limit)
    debates = session.exec(items_stmt).all()
    
    has_more = offset + len(debates) < total
    return {
        "items": debates,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.get("/debates/{debate_id}")
async def get_debate(
    debate_id: str,
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    from repositories.debate_repository import DebateRepository
    repo = DebateRepository(session)
    debate = repo.get_by_id(debate_id)
    debate = require_debate_access(debate, current_user, session)


    # Public users get a stripped-down DTO — no config, routing_meta, etc.
    if not current_user or not is_debate_owner(debate, current_user):
        if is_debate_public(debate):
            ip = request.client.host if (request and request.client) else None
            record_audit(
                "view_shared_debate",
                user_id=current_user.id if current_user else None,
                target_type="debate",
                target_id=debate_id,
                ip_address=ip,
                session=session,
            )
            return serialize_debate_public(debate)
        # Non-public, non-owner access was already rejected by require_debate_access
    return serialize_debate_private(debate)


@router.get("/debates/{debate_id}/report")
async def get_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from services.reporting import build_report
    data = build_report(session, debate_id, current_user)
    return {
        "id": debate_id,
        "prompt": data["debate"].prompt,
        "status": data["debate"].status,
        "final": data["debate"].final_content,
        "scores": [score.model_dump() for score in data["scores"]],
        "rounds": [round_.model_dump() for round_ in data["rounds"]],
        "messages_count": data["messages_count"],
        "created_at": data["debate"].created_at,
        "updated_at": data["debate"].updated_at,
    }


@router.post("/debates/{debate_id}/export")
async def export_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from services.reporting import build_report, report_to_markdown
    
    # Check export quota BEFORE doing expensive work (Patchset 65.B1)
    check_export_quota(session, current_user.id)
    
    # Run heavy export generation in thread pool
    loop = asyncio.get_running_loop()
    content = await loop.run_in_executor(
        None, 
        lambda: report_to_markdown(build_report(session, debate_id, current_user))
    )
    
    # Only increment and commit if export succeeded
    increment_export_usage(session, current_user.id)
    session.commit()
    
    track_metric("exports_generated")
    record_audit(
        "export_markdown",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        session=session,
    )
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{debate_id}.md"'},
    )


@router.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    import time
    start_time = time.time()
    
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)

    # Patchset 107: Using single transaction block / thread safety optimization
    messages = session.exec(
        select(Message).where(Message.debate_id == debate_id).order_by(sa.asc(Message.created_at))
    ).all()
    scores = session.exec(
        select(Score).where(Score.debate_id == debate_id).order_by(sa.asc(Score.created_at))
    ).all()
    pairwise_votes = session.exec(
        select(PairwiseVote)
        .where(PairwiseVote.debate_id == debate_id)
        .order_by(sa.asc(PairwiseVote.created_at))
    ).all()

    events: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "seat":
            meta = message.meta or {}
            events.append(
                {
                    "type": "seat_message",
                    "round": message.round_index,
                    "seat_id": meta.get("seat_id"),
                    "seat_name": message.persona,
                    "role": meta.get("role_profile") or "agent",
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "text": message.content,
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "delegate":
            # Conversation mode messages stored as 'delegate'
            meta = message.meta or {}
            events.append(
                {
                    "type": "seat_message",
                    "round": message.round_index,
                    "seat_id": meta.get("seat_id"),
                    "seat_name": message.persona,
                    "role": "agent",
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "text": message.content,
                    "mode": "conversation",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "arena_response":
            meta = message.meta or {}
            events.append(
                {
                    "type": "arena_response",
                    "round": message.round_index,
                    "model_id": meta.get("model_id"),
                    "display_name": message.persona,
                    "provider": meta.get("provider"),
                    "content": message.content,
                    "logo_url": meta.get("logo_url"),
                    "persona_type": meta.get("persona_type"),
                    "persona_tagline": meta.get("persona_tagline"),
                    "success": meta.get("success", True),
                    "mode": "arena",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role == "arena_synthesis":
            events.append(
                {
                    "type": "arena_synthesis",
                    "round": message.round_index,
                    "actor": "Synthesizer",
                    "role": "synthesizer",
                    "text": message.content,
                    "mode": "arena",
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )
        elif message.role in {"candidate", "revised"}:
            events.append(
                {
                    "type": "message",
                    "round": message.round_index,
                    "actor": message.persona,
                    "role": "agent",
                    "text": message.content,
                    "at": message.created_at.isoformat() if message.created_at else None,
                }
            )

    for score in scores:
        events.append(
            {
                "type": "score",
                "persona": score.persona,
                "judge": score.judge,
                "score": float(score.score),
                "rationale": score.rationale,
                "role": "judge",
                "at": score.created_at.isoformat(),
            }
        )

    for vote in pairwise_votes:
        if vote.winner == "A":
            winner = vote.candidate_a
            loser = vote.candidate_b
        elif vote.winner == "B":
            winner = vote.candidate_b
            loser = vote.candidate_a
        else:
            winner = vote.winner
            loser = vote.candidate_b if winner == vote.candidate_a else vote.candidate_a
        events.append(
            {
                "type": "pairwise",
                "judge_id": vote.judge_id,
                "candidate_a": vote.candidate_a,
                "candidate_b": vote.candidate_b,
                "winner": winner,
                "loser": loser,
                "at": vote.created_at.isoformat(),
            }
        )

    if debate.final_content:
        events.append(
            {
                "type": "final",
                "actor": "Synthesizer",
                "role": "synthesizer",
                "text": debate.final_content,
                "at": debate.updated_at.isoformat() if debate.updated_at else None,
            }
        )

    events.sort(key=lambda e: e.get("at") or "")
    
    elapsed_ms = (time.time() - start_time) * 1000
    if elapsed_ms > 500:
        logger.warning(f"timeline_fetch_slow: debate_id={debate_id} elapsed_ms={elapsed_ms:.1f} events={len(events)}")

    # Filter events for unauthenticated public users — strip internal metadata
    if not current_user and is_debate_public(debate):
        return {"items": serialize_events_public(events)}

    return {"items": events}


@router.get("/debates/{debate_id}/judges")
async def get_debate_judges(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    judges = [{"name": judge.name, "type": getattr(judge, "type", "judge")} for judge in config.judges]
    return {"judges": judges}


@router.get("/debates/{debate_id}/scores.csv")
async def export_scores_csv(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)
    
    # Check export quota BEFORE doing expensive work (Patchset 65.B1)
    check_export_quota(session, current_user.id)
    
    scores = session.exec(select(Score).where(Score.debate_id == debate_id).order_by(sa.asc(Score.created_at))).all()
    if not scores:
        raise NotFoundError(message="No scores found", code="scores.not_found")

    from services.reporting import generate_csv_content
    loop = asyncio.get_running_loop()
    content = await loop.run_in_executor(None, lambda: generate_csv_content(scores))
    
    # Increment and commit after successful generation
    increment_export_usage(session, current_user.id)
    session.commit()
    
    filename = f"scores_{debate_id}.csv"
    record_audit(
        "export_scores_csv",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        session=session,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/debates/{debate_id}/stream-token")
async def get_stream_token(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Generate a short-lived token scoped only to this debate stream."""
    require_debate_access(session.get(Debate, debate_id), current_user, session)
    from auth import create_stream_token
    token = create_stream_token(current_user.id, debate_id)
    return {"token": token, "expires_in": 300}


@router.get("/debates/{debate_id}/replay")
async def replay_events(
    debate_id: str,
    from_sequence: Optional[int] = Query(default=None, description="Start sequence offset (non-inclusive)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    """Retrieve cached real-time events from the memory/Redis event log."""
    require_debate_access(session.get(Debate, debate_id), current_user, session)
    channel_id = debate_channel_id(debate_id)
    
    events = []
    if hasattr(sse_backend, "_history"):
        async with sse_backend._lock:
            history = list(sse_backend._history.get(channel_id, []))
        for env in history:
            if from_sequence is None or env.get("sequence", 0) > from_sequence:
                events.append(env)
    elif hasattr(sse_backend, "_redis"):
        history_key = f"sse:history:{channel_id}"
        try:
            events_str = await sse_backend._redis.lrange(history_key, 0, -1)
            for evt_str in events_str:
                evt = json.loads(evt_str)
                if from_sequence is None or evt.get("sequence", 0) > from_sequence:
                    events.append(evt)
        except Exception as e:
            logger.error(f"Failed to fetch Redis SSE history for replay: {e}")
            
    return {"events": events}


@router.get("/debates/{debate_id}/stream")
async def stream_events(
    debate_id: str,
    request: Request,
    token: Optional[str] = Query(default=None, description="Stream-scoped JWT for EventSource auth fallback"),
    last_sequence: Optional[int] = Query(default=None, description="Last sequence number received by client"),
    session: Session = Depends(get_session),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Resolve user: cookie/Bearer first, then scoped stream token fallback
    # (EventSource API cannot set Authorization header, so token param is needed for 3P clients)
    from auth import get_optional_user, resolve_stream_token
    user = get_optional_user(request=request, session=session)
    if not user and token:
        user = resolve_stream_token(token, session, debate_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="authentication required")

    require_debate_access(session.get(Debate, debate_id), user, session)
    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)
    track_metric("sse_stream_open")

    # Determine last sequence from query param or Last-Event-ID header
    last_seq_val = last_sequence
    if last_seq_val is None and "last-event-id" in request.headers:
        try:
            last_seq_val = int(request.headers["last-event-id"])
        except ValueError:
            pass

    async def eventgen():
        async for event in sse_backend.subscribe(channel_id, last_sequence=last_seq_val):
            seq = event.get("sequence")
            id_prefix = f"id: {seq}\n" if seq is not None else ""
            yield f"{id_prefix}data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # Check either top-level or payload type
            evt_type = event.get("type")
            payload = event.get("payload")
            payload_type = payload.get("type") if isinstance(payload, dict) else None
            if evt_type == "final" or payload_type == "final":
                break

    # Explicit CORS headers — CORSMiddleware does not reliably inject on streaming responses
    allowed_origin = settings.WEB_APP_ORIGIN or "*"
    return StreamingResponse(
        eventgen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )


@router.patch("/debates/{debate_id}")
async def update_debate(
    debate_id: str,
    body: DebateUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    if not (current_user.role == "admin" or debate.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    previous_team = debate.team_id
    if body.team_id is not None:
        if body.team_id == "":
            debate.team_id = None
        else:
            team = session.get(Team, body.team_id)
            if not team:
                raise NotFoundError(message="Team not found", code="team.not_found")
            if not user_is_team_member(session, current_user, team.id):
                raise PermissionError(message="Cannot assign to this team", code="permission.denied")
            debate.team_id = team.id

    session.add(debate)
    session.commit()
    session.refresh(debate)
    if previous_team != debate.team_id:
        record_audit(
            "debate_team_updated",
            user_id=current_user.id,
            target_type="debate",
            target_id=debate.id,
            meta={"team_id": debate.team_id},
            session=session,
        )
    return {
        "id": debate.id,
        "team_id": debate.team_id,
    }


class DebateShare(BaseModel):
    is_public: bool

@router.post("/debates/{debate_id}/share")
async def share_debate(
    debate_id: str,
    body: DebateShare,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    if not (current_user.role == "admin" or debate.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    if not debate.config:
        debate.config = {}
    
    config = dict(debate.config)
    config["is_public"] = body.is_public
    debate.config = config

    session.add(debate)
    session.commit()
    
    # Audit log
    record_audit(
        "debate_shared",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate.id,
        meta={"is_public": body.is_public},
        session=session,
    )
    
    return {"id": debate.id, "is_public": body.is_public}


class DebateModerateRequest(BaseModel):
    round_index: int
    moderation_steering: str


@router.post("/debates/{debate_id}/moderate")
async def moderate_debate(
    debate_id: str,
    body: DebateModerateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from models import DebateTurn
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    if not (current_user.role == "admin" or debate.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    stmt = select(DebateTurn).where(
        DebateTurn.debate_id == debate_id,
        DebateTurn.round_index == body.round_index,
        DebateTurn.agent_id == "moderator"
    )
    turn = session.exec(stmt).first()
    if turn:
        turn.moderation_steering = body.moderation_steering
        session.add(turn)
    else:
        turn = DebateTurn(
            debate_id=debate_id,
            round_index=body.round_index,
            agent_id="moderator",
            moderation_steering=body.moderation_steering
        )
        session.add(turn)
    session.commit()
    session.refresh(turn)

    return {
        "debate_id": debate_id,
        "round_index": body.round_index,
        "moderation_steering": body.moderation_steering
    }


@router.get("/debates/{debate_id}/argument-tree")
async def get_argument_tree(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from models import DebateTurn
    debate = session.get(Debate, debate_id)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    
    stmt = select(DebateTurn).where(DebateTurn.debate_id == debate_id).order_by(DebateTurn.round_index.asc())
    turns = session.exec(stmt).all()

    raw_to_agent = {}
    for t in turns:
        if t.agent_id == "moderator":
            continue
        if t.claims_nodes:
            for node in t.claims_nodes:
                raw_id = node.get("id")
                if raw_id:
                    raw_to_agent[raw_id] = t.agent_id

    nodes = []
    for t in turns:
        # Skip moderator rows for tree nodes, but we could list them if needed.
        if t.agent_id == "moderator":
            continue
        if t.claims_nodes:
            for node in t.claims_nodes:
                target_raw = node.get("rebuts_target")
                target_agent = raw_to_agent.get(target_raw) if target_raw else None
                rebuts_target = f"{target_agent}_{target_raw}" if target_agent else None
                
                nodes.append({
                    "id": f"{t.agent_id}_{node.get('id')}",
                    "raw_id": node.get("id"),
                    "agent_id": t.agent_id,
                    "round_index": t.round_index,
                    "type": node.get("type"),
                    "claim": node.get("claim"),
                    "rebuts_target": rebuts_target,
                    "position_drift": t.position_drift
                })
    return {"nodes": nodes}


# Alias for router inclusion and compatibility
debates_router = router
