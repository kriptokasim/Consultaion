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
    PermissionError,
    ProviderCircuitOpenError,
    RateLimitError,
    ValidationError,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from integrations.langfuse import start_debate_trace
from models import Debate, DebateContinuation, Team, User, utcnow
from parliament.model_registry import list_enabled_models
from parliament.providers import PROVIDERS
from parliament.roles import ROLE_PROFILES
from parliament.router_v2 import RouteContext, choose_model
from parliament.schemas import TimelineEvent
from parliament.timeline import build_debate_timeline
from ratelimit import increment_ip_bucket, record_429
from schemas import (
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
    is_debate_owner,
    is_debate_public,
    require_debate_access,
    require_debate_mutation_access,
    require_schema_current,
    track_metric,
    user_is_team_member,
)
from routes.debates.schemas import DebateListResponse, DebateUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


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
    # Track timeline fetch performance
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
    require_schema_current(session)
    # OT-12: Track debate creation via PostHog
    try:
        from integrations.posthog import track_event as _ph_track
        _ph_track("debate_created", str(current_user.id), {
            "mode": body.mode,
            "seat_count": len(body.panel_config.seats) if body.panel_config else 4,
            "prompt_length": len(body.prompt) if body.prompt else 0,
        })
    except Exception:
        pass

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
        from billing.service import increment_debate_usage
        increment_debate_usage(session, current_user.id)
    except RateLimitError as exc:
        payload = {
            "code": "rate_limit",
            "reason": exc.code,
            "detail": exc.detail,
            "reset_at": exc.reset_at,
        }
        from audit import record_audit
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

        # Validate config with JSON contract
        from json_contracts import safe_validate_config
        validated_config = safe_validate_config(config)
        if validated_config:
            config = validated_config.model_dump()

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
        run_attempt=1,
    )
    session.add(debate)

    # FH125 G-7: Create initial DebateAttempt
    from models import DebateAttempt
    attempt = DebateAttempt(
        debate_id=debate_id,
        attempt_number=1,
        status="queued",
        model_id=best_model_id,
        created_at=utcnow(),
    )
    session.add(attempt)
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

    from audit import record_audit
    record_audit(
        "debate_created",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        meta={"prompt": body.prompt},
        session=session,
    )
    track_metric("debates_created")
    # Track mode usage metrics
    mode = body.mode or "conversation"
    # Replaced legacy mode.{mode}.started with consistent mode.debate.started 
    # and tracking the specific mode as a tag or sub-metric if needed, but for now just:
    track_metric(f"mode.debate.{mode}.started")

    # OT-12: Track debate start via PostHog
    try:
        from integrations.posthog import track_event as _ph_track
        _ph_track("debate_started", str(current_user.id), {
            "debate_id": debate_id,
            "mode": mode,
        })
    except Exception:
        pass

    return {"id": debate_id}


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
    )
    if filters:
        base_query = base_query.where(*filters)

    # Caching for total count
    # Use shared Redis connection pool
    total = None
    cache_key = None
    redis_client = None
    if settings.REDIS_URL:
        try:
            from redis_pool import get_sync_redis_client
            redis_client = get_sync_redis_client()
            if redis_client:
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

    from observability.tracing import traced_span
    with traced_span("debate.list", {"limit": str(limit), "offset": str(offset), "status": str(status)}):
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
    from observability.tracing import traced_span
    with traced_span("debate.read", {"debate_id": debate_id, "mode": "api"}):
        from repositories.debate_repository import DebateRepository
        repo = DebateRepository(session)
        debate = repo.get_by_id(debate_id)
        debate = require_debate_access(debate, current_user, session)

    # Validate JSON contracts on read
    if debate.config:
        from json_contracts import safe_validate_config
        validated = safe_validate_config(debate.config)
        if validated:
            debate.config = validated.model_dump()
    if debate.final_meta:
        from json_contracts import safe_validate_final_meta
        validated = safe_validate_final_meta(debate.final_meta)
        if validated:
            debate.final_meta = validated.model_dump()

    # Fetch latest continuation status
    stmt = (
        select(DebateContinuation)
        .where(DebateContinuation.debate_id == debate_id)
        .order_by(DebateContinuation.created_at.desc())
    )
    continuation = session.execute(stmt).scalars().first()
    continuation_status = continuation.status if continuation else None


    # Public users get a stripped-down DTO — no config, routing_meta, etc.
    if not current_user or not is_debate_owner(debate, current_user):
        if is_debate_public(debate):
            ip = request.client.host if (request and request.client) else None
            from audit import record_audit
            record_audit(
                "view_shared_debate",
                user_id=current_user.id if current_user else None,
                target_type="debate",
                target_id=debate_id,
                ip_address=ip,
                session=session,
            )
            from serializers import serialize_debate_public
            return serialize_debate_public(debate, continuation_status=continuation_status, session=session)
        # Non-public, non-owner access was already rejected by require_debate_access
    from serializers import serialize_debate_private
    return serialize_debate_private(debate, continuation_status=continuation_status, session=session)


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


@router.patch("/debates/{debate_id}")
async def update_debate(
    debate_id: str,
    body: DebateUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = require_debate_mutation_access(session.get(Debate, debate_id), current_user, session)

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
        from audit import record_audit
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
