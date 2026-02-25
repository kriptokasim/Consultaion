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
    members_from_config,
    require_debate_access,
    serialize_rating_persona,
    track_metric,
    user_is_team_member,
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
    current_user: User = Depends(get_current_user),
):
    debate = session.get(Debate, debate_id)
    debate = require_debate_access(debate, current_user, session)
    if not debate:
        raise NotFoundError(message="Debate not found", code="debate.not_found")
    
    # Return partial timeline for running debates instead of erroring
    timeline = build_debate_timeline(session, debate)
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
    ip = request.client.host if request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, settings.RL_DEBATE_CREATE_WINDOW, settings.RL_DEBATE_CREATE_MAX_CALLS)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
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

    # Patchset 57.0: Check if account is disabled
    from fastapi import HTTPException
    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_disabled",
                "message": "Your account has been disabled. Please contact support.",
            }
        )

    # Patchset 55.0: Check quota before debate creation
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
    from billing.service import get_active_plan
    plan = get_active_plan(session, current_user.id)
    allowed_tiers = plan.limits.get("allowed_model_tiers")
    
    # If allowed_tiers is not set, default to ["standard"] for Free plans (is_default_free=True)
    # and ["standard", "advanced"] for others, unless explicitly configured.
    if allowed_tiers is None:
        if plan.is_default_free:
            allowed_tiers = ["standard"]
        else:
            allowed_tiers = ["standard", "advanced"]
            
    # Check the model's tier
    from parliament.model_registry import get_default_model
    target_model_id = body.model_id or get_default_model().id
    target_model_info = enabled_models.get(target_model_id)
    if target_model_info:
        model_tier = getattr(target_model_info, "tier", "standard")
        if model_tier not in allowed_tiers:
             raise ValidationError(
                message=f"Model '{target_model_info.display_name}' is not available on your plan.",
                code="debate.model_tier_restricted",
                hint="Please upgrade to Pro to use advanced models."
            )

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
    debate = Debate(
        id=debate_id,
        prompt=body.prompt,
        status="queued",
        config=config_payload,
        user_id=current_user.id,
        model_id=best_model_id,
        routed_model=best_model_id,
        routing_policy=body.routing_policy,
        routing_meta={
            "candidates": [c.model_dump() for c in candidates],
            "requested_model": body.model_id,
        },
        panel_config=panel.model_dump(),
        engine_version=panel.engine_version,
    )
    session.add(debate)
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
    return {"id": debate_id}


@router.post("/debates/{debate_id}/start")
async def start_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    if not settings.DISABLE_AUTORUN:
        raise ValidationError(message="Manual start is disabled", code="debate.manual_start_disabled")
    debate = session.get(Debate, debate_id)
    debate = require_debate_access(debate, current_user, session)
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


@router.get("/debates")
async def list_debates(
    status: Optional[str] = Query(default=None),
    limit: int = Query(20, ge=1, le=200),
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
            filters.append(sa.func.lower(Debate.prompt).contains(query_text.lower()))

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
    total = None
    cache_key = None
    redis_client = None
    if settings.REDIS_URL:
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            # Create a simple cache key based on filters (this is a simplification)
            # For strict correctness, we'd hash the compiled query params, but here we rely on user_id/status/q
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
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = session.get(Debate, debate_id)
    return require_debate_access(debate, current_user, session)


@router.get("/debates/{debate_id}/report")
async def get_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
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
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)

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


@router.get("/debates/{debate_id}/stream")
async def stream_events(
    debate_id: str,
    request: Request,
    token: Optional[str] = Query(default=None, description="JWT for EventSource auth fallback"),
    session: Session = Depends(get_session),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    # Resolve user: cookie/Bearer first, then query token fallback
    # (EventSource API cannot set Authorization header, so token param is needed)
    from auth import get_optional_user, resolve_user_from_token
    user = get_optional_user(request=request, session=session)
    if not user and token:
        user = resolve_user_from_token(token, session)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="authentication required")

    require_debate_access(session.get(Debate, debate_id), user, session)
    channel_id = debate_channel_id(debate_id)
    await sse_backend.create_channel(channel_id)
    track_metric("sse_stream_open")

    async def eventgen():
        async for event in sse_backend.subscribe(channel_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") == "final":
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


# Alias for router inclusion and compatibility
debates_router = router
