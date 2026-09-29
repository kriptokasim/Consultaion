import logging
import re
import uuid
from typing import Optional

import sqlalchemy as sa
from auth import (
    get_current_user_flexible,
    get_optional_user_flexible,
)
from channels import debate_channel_id
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
from parliament.model_registry import (
    ARENA_MODELS,
    list_enabled_models_for_user,
    resolve_model_info,
)
from parliament.providers import PROVIDERS
from parliament.roles import ROLE_PROFILES
from parliament.router_v2 import RouteContext, choose_model
from parliament.schemas import TimelineEvent
from parliament.timeline import build_debate_timeline
from ratelimit import increment_ip_bucket, record_429
from schemas import (
    DebateCreate,
    PanelConfig,
    PanelSeat,
    default_debate_config,
    default_panel_config,
)
from sqlalchemy import func
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend
from usage_limits import refund_run_slot, reserve_run_slot

from config import settings
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

# A client-generated key identifying one "start run" intent. Retries and double
# submits that carry the same key return the run the first request created
# instead of reserving quota and credits for a second one.
_IDEMPOTENCY_HEADER = "X-Idempotency-Key"
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_CREATE_REQUEST_LEDGER_KIND = "debate_create_request"


def _create_idempotency_ledger_key(request: Request, user_id: str) -> str | None:
    raw = request.headers.get(_IDEMPOTENCY_HEADER) or request.headers.get("Idempotency-Key")
    if raw is None:
        return None
    raw = raw.strip()
    if not _IDEMPOTENCY_KEY_RE.match(raw):
        raise ValidationError(
            message="Invalid idempotency key.",
            code="debate.invalid_idempotency_key",
            hint="Use 8-128 letters, digits, '.', '_', ':' or '-'.",
        )
    return f"debate_create:{user_id}:{raw}"


def _replayed_create_response(session: Session, ledger_key: str, user_id: str) -> dict | None:
    """Return the original response for a create request already accepted."""
    from models import UsageLedgerEntry

    entry = session.exec(
        select(UsageLedgerEntry).where(UsageLedgerEntry.idempotency_key == ledger_key)
    ).first()
    if entry is None or entry.user_id != user_id or not entry.debate_id:
        return None
    debate = session.get(Debate, entry.debate_id)
    if debate is None:
        return None
    track_metric("debate.create.idempotent_replay")
    return _create_response_payload(debate.id, debate.status, debate.config or {}, replayed=True)


def _create_response_payload(
    debate_id: str,
    status: str,
    config_payload: dict,
    *,
    enabled_models_count: int | None = None,
    replayed: bool = False,
) -> dict:
    dispatch_mode = (settings.DEBATE_DISPATCH_MODE or "inline").lower()
    queue_name = None
    if dispatch_mode == "celery":
        from debate_dispatch import choose_queue_for_debate
        queue_name = choose_queue_for_debate(config_payload, settings)

    payload: dict = {
        "id": debate_id,
        "status": status,
        "autorun": not settings.DISABLE_AUTORUN,
        "dispatch_mode": dispatch_mode,
        "queue": queue_name,
        "worker_required": dispatch_mode == "celery",
        # Which provider keys this deployment holds is operator information,
        # not something to hand every caller; only the model count is exposed.
        "diagnostics": {"enabled_models_count": enabled_models_count},
    }
    if replayed:
        payload["idempotent_replay"] = True
    if settings.DISABLE_AUTORUN:
        payload["warning"] = (
            "Autorun is disabled; this run will remain queued until manually dispatched."
        )
    return payload


def _validate_compare_models(
    requested: Optional[list[str]],
    enabled_models: dict,
) -> list[str]:
    """Validate Compare mode model selection at the create boundary.

    Every requested model must be canonical (known), enabled for the user
    (covers provider validity and BYOK/hosted availability), tier-allowed by
    the user's plan, and unique after normalization. At least two valid
    UNIQUE models are required — raw ``len(requested) >= 2`` is not enough.

    Returns the deduplicated validated list. Raises ValidationError otherwise.
    """
    if not requested or not isinstance(requested, list):
        raise ValidationError(
            message="Compare mode requires at least 2 models",
            code="debate.invalid_compare_models",
        )

    seen: set[str] = set()
    validated: list[str] = []
    for raw in requested:
        if not isinstance(raw, str) or not raw.strip():
            raise ValidationError(
                message="Invalid model in compare selection",
                code="debate.invalid_compare_models",
            )
        model_id = raw.strip()
        # ``enabled_models`` is the user-scoped view of the canonical model
        # registry: membership covers known/enabled/provider-valid and
        # BYOK/hosted availability for this user. Tier gating happens after
        # the hosted-credit extension of ``allowed_tiers`` so a free-plan
        # user may select advanced models through the per-run credit policy.
        info = enabled_models.get(model_id)
        if info is None:
            raise ValidationError(
                message=f"Model '{model_id}' is invalid, disabled, or unavailable to you",
                code="debate.invalid_compare_models",
            )
        if model_id not in seen:
            seen.add(model_id)
            validated.append(model_id)

    if len(validated) < 2:
        raise ValidationError(
            message="Compare mode requires at least 2 distinct valid models",
            code="debate.invalid_compare_models",
        )
    return validated


@router.get("/debates/{debate_id}/timeline", response_model=list[TimelineEvent])
async def get_debate_timeline(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user_flexible),
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
    current_user: User = Depends(get_current_user_flexible),
    sse_backend: BaseSSEBackend = Depends(get_sse_backend),
):
    require_schema_current(session)

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

    user_id = current_user.id
    # Replays are answered before any rate-limit or quota accounting: the
    # original request already paid for the run.
    idempotency_ledger_key = _create_idempotency_ledger_key(request, user_id)
    if idempotency_ledger_key:
        replay = _replayed_create_response(session, idempotency_ledger_key, user_id)
        if replay is not None:
            return replay

    # 2. IP Rate Limit Check
    # Behind the platform proxy request.client is the proxy, so every user
    # would share one bucket; resolve the client through the trusted-proxy list.
    from middleware.rate_limit_identity import _get_trusted_client_ip
    ip = _get_trusted_client_ip(request)
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
    slot_reserved = False
    try:
        reserve_run_slot(session, current_user.id)
        slot_reserved = True
        from billing.service import increment_debate_usage
        increment_debate_usage(session, current_user.id)
    except RateLimitError as exc:
        if slot_reserved:
            try:
                # The monthly increment is only staged; roll it back and refund
                # the committed hourly slot (owner-aware, floor-guarded).
                session.rollback()
                refund_run_slot(session, user_id)
            except Exception as refund_err:
                logger.error(f"Failed to refund reserved slot on rate limit block: {refund_err}")
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

        # DebateCreate.config is already validated by the production Pydantic
        # schema. Serialize it once and keep that dict as the canonical payload.
        # The versioned JSON contract is a compatibility check only: its legacy
        # nested schema must never replace/drop production fields.
        config_model = body.config or default_debate_config()
        config_payload = config_model.model_dump()
        from json_contracts import safe_validate_config
        if safe_validate_config(config_payload) is None:
            logger.warning(
                "debate_config_contract_validation_failed",
                extra={"user_id": current_user.id, "mode": str(body.mode)},
            )

        enabled_models = {m.id: m for m in list_enabled_models_for_user(current_user.id)}
        if not enabled_models:
            # Patchset 136: No models available — fail before further processing.
            # Quota was already reserved (line 140); the outer except block refunds it.
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

        # Compare mode: full entitlement validation BEFORE any billing
        # reservation — invalid input must never consume quota or credits.
        validated_compare_models: list[str] | None = None
        if body.mode == "compare":
            validated_compare_models = _validate_compare_models(
                requested=body.compare_models,
                enabled_models=enabled_models,
            )

        # Check the model's tier
        from parliament.model_registry import get_default_model
        target_model_id = body.model_id or get_default_model().id
        target_model_info = enabled_models.get(target_model_id)
        model_tier = "standard"
        if target_model_info:
            model_tier = getattr(target_model_info, "tier", "standard")

        compare_has_advanced = bool(
            validated_compare_models
            and any(
                getattr(enabled_models.get(m), "tier", "standard") == "advanced"
                for m in validated_compare_models
            )
        )

        # Phase 8: Hosted Credits check for Free plan users - only for advanced/SOTA models.
        # Product policy (per-run reservation unit): a free-plan run that will
        # execute ANY advanced/SOTA model requires exactly one hosted credit
        # reservation for the run. Arena always executes advanced fan-out;
        # Compare requires one when any selected model is advanced.
        is_sota_run = (
            model_tier == "advanced"
            or body.mode == "arena"
            or compare_has_advanced
        )
        # Reservation happens after debate_id is assigned (durable ledger key).
        needs_hosted_credit = bool(plan.is_default_free and is_sota_run)
        credit_reservation_id: str | None = None

        allowed_tiers = plan.limits.get("allowed_model_tiers")

        # If allowed_tiers is not set, default to ["standard"] for Free plans (is_default_free=True)
        # and ["standard", "advanced"] for others, unless explicitly configured.
        if allowed_tiers is None:
            if plan.is_default_free:
                allowed_tiers = ["standard"]
            else:
                allowed_tiers = ["standard", "advanced"]

        # Free tier users may use advanced models when a hosted credit will be reserved
        if plan.is_default_free and needs_hosted_credit:
            allowed_tiers = list(allowed_tiers)
            if "advanced" not in allowed_tiers:
                allowed_tiers.append("advanced")

        if model_tier not in allowed_tiers:
             raise ValidationError(
                message=f"Model '{target_model_info.display_name if target_model_info else target_model_id}' is not available on your plan.",
                code="debate.model_tier_restricted",
                hint="Please upgrade to Pro to use advanced models."
            )

        # Compare models: re-check tiers AFTER the free-plan hosted-credit
        # extension of allowed_tiers so the policy matches single-model runs.
        if validated_compare_models:
            for m in validated_compare_models:
                tier = getattr(enabled_models.get(m), "tier", "standard")
                if tier not in allowed_tiers:
                    raise ValidationError(
                        message=f"Model '{m}' is not available on your plan.",
                        code="debate.model_tier_restricted",
                        hint="Please upgrade to Pro to use advanced models.",
                    )

        if body.mode == "arena" and body.panel_config is None:
            default_arena_models = [
                enabled_models[model_id]
                for model_id in ARENA_MODELS
                if model_id in enabled_models
            ]
            if not default_arena_models:
                default_arena_models = list(enabled_models.values())[:4]
            panel_config = PanelConfig(
                seats=[
                    PanelSeat(
                        seat_id=model.id,
                        display_name=model.display_name,
                        provider_key="google" if model.provider == "gemini" else model.provider,
                        model=model.id,
                        role_profile="architect",
                        temperature=0.7,
                    )
                    for model in default_arena_models
                ]
            )
        elif body.mode == "debate" and body.panel_config is None:
            eligible_debate_models = [
                model
                for model in enabled_models.values()
                if getattr(model, "tier", "standard") in allowed_tiers
            ]
            if not eligible_debate_models:
                raise ProviderCircuitOpenError(
                    message="No Structured Debate models are available on your plan.",
                    code="models.unavailable",
                    hint="Configure a provider or select another model.",
                )
            role_template = default_panel_config()
            panel_config = role_template.model_copy(
                update={
                    "seats": [
                        seat.model_copy(
                            update={
                                "provider_key": (
                                    "google" if model.provider == "gemini" else model.provider
                                ),
                                "model": model.id,
                            }
                        )
                        for seat, model in (
                            (
                                seat,
                                eligible_debate_models[index % len(eligible_debate_models)],
                            )
                            for index, seat in enumerate(role_template.seats)
                        )
                    ]
                }
            )
        else:
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

        if body.mode == "arena":
            normalized_seats: list[PanelSeat] = []
            seen_model_ids: set[str] = set()
            for seat in panel.seats:
                model_info = resolve_model_info(seat.model)
                if model_info is None or model_info.id not in enabled_models:
                    raise ValidationError(
                        message=f"Model '{seat.model}' is invalid or unavailable.",
                        code="debate.invalid_model",
                        hint="Please select a currently available model.",
                    )

                expected_provider = "google" if model_info.provider == "gemini" else model_info.provider
                if seat.provider_key != expected_provider:
                    raise ValidationError(
                        message=(
                            f"Model '{seat.model}' does not belong to provider "
                            f"'{seat.provider_key}'."
                        ),
                        code="debate.invalid_provider",
                    )
                if model_info.tier not in allowed_tiers:
                    raise ValidationError(
                        message=f"Model '{model_info.display_name}' is not available on your plan.",
                        code="debate.model_tier_restricted",
                        hint="Please upgrade to Pro or select a standard model.",
                    )
                if model_info.id in seen_model_ids:
                    continue

                seen_model_ids.add(model_info.id)
                normalized_seats.append(
                    seat.model_copy(
                        update={
                            "seat_id": model_info.id,
                            "display_name": model_info.display_name,
                            "provider_key": expected_provider,
                            "model": model_info.id,
                        }
                    )
                )

            if not normalized_seats:
                raise ProviderCircuitOpenError(
                    message="No Arena models are available.",
                    code="models.unavailable",
                    hint="Configure a provider or select another model.",
                )
            panel = panel.model_copy(update={"seats": normalized_seats})

        elif body.mode == "debate":
            normalized_debate_seats: list[PanelSeat] = []
            for seat in panel.seats:
                model_info = resolve_model_info(seat.model)
                if model_info is None or model_info.id not in enabled_models:
                    raise ValidationError(
                        message=f"Model '{seat.model}' is invalid or unavailable.",
                        code="debate.invalid_model",
                        hint="Please select a currently available model.",
                    )

                expected_provider = (
                    "google" if model_info.provider == "gemini" else model_info.provider
                )
                if seat.provider_key != expected_provider:
                    raise ValidationError(
                        message=(
                            f"Model '{seat.model}' does not belong to provider "
                            f"'{seat.provider_key}'."
                        ),
                        code="debate.invalid_provider",
                    )
                if model_info.tier not in allowed_tiers:
                    raise ValidationError(
                        message=f"Model '{model_info.display_name}' is not available on your plan.",
                        code="debate.model_tier_restricted",
                        hint="Please upgrade to Pro or select a standard model.",
                    )

                # Keep the seat identity/display role intact. Structured Debate
                # may intentionally assign one model to several distinct roles.
                normalized_debate_seats.append(
                    seat.model_copy(
                        update={
                            "provider_key": expected_provider,
                            "model": model_info.id,
                        }
                    )
                )

            if not normalized_debate_seats:
                raise ProviderCircuitOpenError(
                    message="No requested panel models are available.",
                    code="models.unavailable",
                    hint="Configure a provider or select another model.",
                )
            panel = panel.model_copy(update={"seats": normalized_debate_seats})

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

        if needs_hosted_credit:
            try:
                credit_reservation_id = reserve_hosted_credit(
                    session,
                    current_user.id,
                    debate_id=debate_id,
                    run_attempt=1,
                )
            except ValidationError as exc:
                if exc.code == "hosted_credits.exhausted" and body.model_id is not None:
                    raise ValidationError(
                        message=f"Model '{target_model_info.display_name if target_model_info else target_model_id}' is not available on your plan.",
                        code="debate.model_tier_restricted",
                        hint="Please upgrade to Pro to use advanced models."
                    ) from exc
                raise exc

        # Patchset 41.0: Start Langfuse trace
        trace_id = start_debate_trace(
            debate_id=debate_id,
            user_id=str(current_user.id),
            routed_model=best_model_id,
            routing_policy=body.routing_policy,
        )

        # Store locale in config so the engine can instruct LLMs to respond in user's language
        if body.locale:
            config_payload["locale"] = body.locale
        if body.mode == "compare":
            # Validated earlier (pre-reservation) via _validate_compare_models.
            config_payload["compare_models"] = validated_compare_models

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
            # The execution lease increments this to attempt 1 when work starts.
            run_attempt=0,
            credit_reservation_id=credit_reservation_id,
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
        if idempotency_ledger_key:
            # Same transaction as the debate: the unique ledger key makes a
            # concurrent duplicate fail at commit instead of creating a run.
            from models import UsageLedgerEntry
            session.add(
                UsageLedgerEntry(
                    user_id=user_id,
                    kind=_CREATE_REQUEST_LEDGER_KIND,
                    status="settled",
                    idempotency_key=idempotency_ledger_key,
                    amount=0,
                    debate_id=debate_id,
                )
            )
        session.commit()

    except Exception as exc:
        # Only the hourly run slot is committed at this point (by
        # reserve_run_slot). The monthly usage increment, any hosted-credit
        # reservation and the debate rows are still pending in this
        # transaction, so rolling back undoes them exactly. Rolling back first
        # also recovers a session that a database error left unusable; the old
        # in-transaction refund then failed to commit and leaked the slot.
        try:
            session.rollback()
            refund_run_slot(session, user_id)
        except Exception as refund_err:
            logger.error(f"Failed to refund quotas during creation failure: {refund_err}")
        if idempotency_ledger_key:
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError):
                # Lost a race with a concurrent request carrying the same key.
                session.rollback()
                replay = _replayed_create_response(session, idempotency_ledger_key, user_id)
                if replay is not None:
                    return replay
        raise exc

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

    # Patchset 136: Dispatch observability metric
    from routes.common import track_metric
    track_metric("debate.create.accepted")
    if not settings.DISABLE_AUTORUN:
        track_metric("debate.dispatch.scheduled")

    # Same default as the Debate row, so analytics match what actually ran.
    mode = body.mode or "arena"
    from audit import record_audit
    # The debate row was already committed above. Persist telemetry in its own
    # transaction because the request-scoped session does not commit on teardown.
    # Do not copy raw prompts into the audit log; length + mode are sufficient
    # for product analytics and materially reduce sensitive-data retention.
    record_audit(
        "debate_created",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        meta={"mode": str(mode), "prompt_length": len(body.prompt)},
    )
    track_metric("debates_created")
    # Track mode usage metrics
    # Replaced legacy mode.{mode}.started with consistent mode.debate.started
    # and tracking the specific mode as a tag or sub-metric if needed, but for now just:
    track_metric(f"mode.debate.{mode}.started")

    # OT-12: Track debate creation and start via PostHog. Emitted only once the
    # run exists, so rejected requests do not count as created debates.
    try:
        from integrations.posthog import track_event as _ph_track
        _ph_track("debate_created", str(current_user.id), {
            "mode": mode,
            "seat_count": len(panel.seats),
            "prompt_length": len(body.prompt) if body.prompt else 0,
        })
        _ph_track("debate_started", str(current_user.id), {
            "debate_id": debate_id,
            "mode": mode,
        })
    except Exception:
        pass

    # Patchset 136: Expanded response with run pipeline diagnostics
    return _create_response_payload(
        debate_id,
        "queued",
        config_payload,
        enabled_models_count=len(enabled_models),
    )


@router.get("/debates", response_model=DebateListResponse)
async def list_debates(
    status: Optional[str] = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user_flexible),
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
            _search_term = f"%{query_text.lower()}%"
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
                import hashlib
                key_parts = [str(current_user.id), str(status), str(q)]
                # Separator matters: joining bare strings makes
                # ("run", "ningx") and ("running", "x") the same cache key, so
                # one filter's total is served for another's query.
                key_str = "\x00".join(key_parts)
                cache_hash = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
                cache_key = f"count:debates:{cache_hash}"
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
    current_user: Optional[User] = Depends(get_optional_user_flexible),
):
    from observability.tracing import traced_span
    with traced_span("debate.read", {"debate_id": debate_id, "mode": "api"}):
        from repositories.debate_repository import DebateRepository
        repo = DebateRepository(session)
        debate = repo.get_by_id(debate_id)
        debate = require_debate_access(debate, current_user, session)

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
            # Public reads do not otherwise mutate the request-scoped session.
            # Use the audit helper's committed standalone transaction so the
            # PLG view event survives request teardown.
            record_audit(
                "view_shared_debate",
                user_id=current_user.id if current_user else None,
                target_type="debate",
                target_id=debate_id,
                ip_address=ip,
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
    current_user: User = Depends(get_current_user_flexible),
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
    current_user: User = Depends(get_current_user_flexible),
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
        )
    return {
        "id": debate.id,
        "team_id": debate.team_id,
    }
