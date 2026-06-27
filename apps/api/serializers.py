"""
Public-safe and private DTO serializers for the Debate model.

Prevents internal field leakage to unauthenticated public users while
preserving full data for owners and admins.

Security principle: Public access means read-only access to a safe public
representation, not full access to the internal Debate object.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public-safe DTOs
# ---------------------------------------------------------------------------

class PublicModelResponse(BaseModel):
    """Safe model response for public consumption."""
    model_id: str
    display_name: str
    provider: str
    content: str
    logo_url: Optional[str] = None
    persona_type: Optional[str] = None
    persona_tagline: Optional[str] = None
    success: bool = True


class PublicDebateDTO(BaseModel):
    """
    Safe subset of Debate fields for unauthenticated public access.

    This DTO intentionally excludes:
    - config (full agent/judge/budget/routing configuration)
    - routing_meta (candidate model scores, routing decisions)
    - panel_config (seat configuration with provider keys)
    - user_id (debate owner identity)
    - team_id (team affiliation)
    - runner_id, lease_expires_at, last_heartbeat_at, run_attempt (worker internals)
    - full final_meta (may contain internal error details)
    """
    id: str
    prompt: str
    status: str
    mode: str
    created_at: datetime
    updated_at: datetime
    final_content: Optional[str] = None
    is_public: bool = True
    model_id: Optional[str] = None
    routed_model: Optional[str] = None
    continuation_status: Optional[str] = None

    # Safe subset of final_meta
    successful_count: Optional[int] = None
    total_count: Optional[int] = None
    synthesis_success: Optional[bool] = None
    models: Optional[List[Dict[str, Any]]] = None
    synthesis_report: Optional[Dict[str, Any]] = None
    synthesis_status: Optional[str] = None
    synthesis_error: Optional[str] = None
    fallback_model: Optional[str] = None
    fallback_reason: Optional[str] = None
    fallback_response: Optional[Dict[str, Any]] = None
    semantic_analysis: Optional[Dict[str, Any]] = None
    divergence_breakdown: Optional[Dict[str, Any]] = None

    # Extra fields for continuous workspace
    current_stage: Optional[str] = None
    stage_checkpoints: Optional[List[Dict[str, Any]]] = None
    continuation_id: Optional[str] = None
    perspectives_ready_at: Optional[datetime] = None
    responses_received: Optional[int] = None
    models_expected: Optional[int] = None
    scores_received: Optional[int] = None
    verification_status: Optional[str] = None

    # Degradation metadata (public-safe generic indicator)
    read_quality: str = "full"
    query_failures: list[str] = []


class PrivateDebateDTO(BaseModel):
    """
    Full Debate data for authenticated owners and admins.

    Includes all fields that the owner needs for management.
    """
    id: str
    prompt: str
    status: str
    mode: str
    created_at: datetime
    updated_at: datetime
    final_content: Optional[str] = None
    is_public: bool = False
    model_id: Optional[str] = None
    routed_model: Optional[str] = None
    routing_policy: Optional[str] = None
    continuation_status: Optional[str] = None

    # Full metadata for owners
    config: Optional[Dict[str, Any]] = None
    panel_config: Optional[Dict[str, Any]] = None
    routing_meta: Optional[Dict[str, Any]] = None
    final_meta: Optional[Dict[str, Any]] = None
    engine_version: Optional[str] = None

    # P143: Mirror safe synthesis fields at top level for frontend consistency.
    # These are the same fields PublicDebateDTO already exposes.
    # Owner already has full final_meta; this is a convenience alias.
    synthesis_report: Optional[Dict[str, Any]] = None
    synthesis_status: Optional[str] = None
    synthesis_error: Optional[str] = None
    synthesis_success: Optional[bool] = None
    fallback_model: Optional[str] = None
    fallback_reason: Optional[str] = None
    fallback_response: Optional[Dict[str, Any]] = None
    semantic_analysis: Optional[Dict[str, Any]] = None
    divergence_breakdown: Optional[Dict[str, Any]] = None
    successful_count: Optional[int] = None
    total_count: Optional[int] = None
    models: Optional[List[Dict[str, Any]]] = None

    # Ownership
    user_id: Optional[str] = None
    team_id: Optional[str] = None

    # Worker internals (admin/owner diagnostics)
    runner_id: Optional[str] = None
    run_attempt: int = 0

    # Extra fields for continuous workspace
    current_stage: Optional[str] = None
    stage_checkpoints: Optional[List[Dict[str, Any]]] = None
    continuation_id: Optional[str] = None
    perspectives_ready_at: Optional[datetime] = None
    responses_received: Optional[int] = None
    models_expected: Optional[int] = None
    scores_received: Optional[int] = None
    verification_status: Optional[str] = None

    # Degradation metadata (private — includes missing capabilities)
    read_quality: str = "full"
    missing_capabilities: list[str] = []
    query_failures: list[str] = []


class PublicDebateEventDTO(BaseModel):
    """Safe event for public consumption — excludes internal seat_id and raw meta."""
    type: str
    round: Optional[int] = None
    display_name: Optional[str] = None
    provider: Optional[str] = None
    content: Optional[str] = None
    text: Optional[str] = None
    logo_url: Optional[str] = None
    persona_type: Optional[str] = None
    persona_tagline: Optional[str] = None
    success: Optional[bool] = None
    mode: Optional[str] = None
    at: Optional[str] = None

    # Score events
    persona: Optional[str] = None
    judge: Optional[str] = None
    score: Optional[float] = None
    rationale: Optional[str] = None
    role: Optional[str] = None
    actor: Optional[str] = None

    # Pairwise events
    candidate_a: Optional[str] = None
    candidate_b: Optional[str] = None
    winner: Optional[str] = None
    loser: Optional[str] = None
    judge_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Serializer functions
# ---------------------------------------------------------------------------

def _safe_final_meta(final_meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract only public-safe fields from final_meta."""
    if not final_meta:
        return {}
    safe = {}
    # Only expose aggregate stats, not internal errors or debug info
    for key in (
        "successful_count",
        "total_count",
        "synthesis_success",
        "models",
        "synthesis_report",
        "synthesis_status",
        "synthesis_error",
        "fallback_model",
        "fallback_reason",
        "fallback_response",
        "semantic_analysis",
        "divergence_breakdown",
    ):
        if key in final_meta:
            val = final_meta[key]
            if key == "models" and isinstance(val, list):
                # Sanitize model entries — keep only display-safe fields
                safe_models = []
                for m in val:
                    if isinstance(m, dict):
                        safe_models.append({
                            "model_id": m.get("model_id"),
                            "display_name": m.get("display_name"),
                            "provider": m.get("provider"),
                            "logo_url": m.get("logo_url"),
                            "persona_type": m.get("persona_type"),
                            "persona_tagline": m.get("persona_tagline"),
                            "success": m.get("success", True),
                        })
                safe["models"] = safe_models
            else:
                safe[key] = val
    return safe


def _get_models_expected(debate) -> int:
    """Safely calculate models_expected from config or registry."""
    config = debate.config or {}
    mode = getattr(debate, "mode", "arena")
    if mode == "arena":
        from parliament.model_registry import get_arena_models
        try:
            return len(get_arena_models())
        except Exception:
            return 4
    agents = config.get("agents", [])
    return len(agents) if agents else 3


def merge_non_null(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge incoming into base, only overwriting keys where incoming has a non-None value."""
    merged = dict(base)
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value
    return merged


def _get_debate_extra_fields(debate, session=None, continuation_status: Optional[str] = None) -> dict:
    """Fetch enrichment fields with schema capability gating and savepoint isolation."""
    from services.schema_capabilities import get_registry, get_schema_capabilities

    res: dict[str, Any] = {
        "current_stage": debate.status,
        "stage_checkpoints": None,
        "continuation_id": None,
        "continuation_status": continuation_status or getattr(debate, "continuation_status", None),
        "perspectives_ready_at": None,
        "responses_received": None,
        "models_expected": None,
        "scores_received": None,
        "verification_status": (debate.final_meta or {}).get("verification_status"),
    }

    res["models_expected"] = _get_models_expected(debate)

    if session:
        try:
            registry = get_registry()
            caps = get_schema_capabilities(session, registry)
        except Exception:
            caps = None

        if caps:
            from services.debate_enrichment import safe_query_extra_fields
            safe_extra = safe_query_extra_fields(debate.id, session, caps)
            res = merge_non_null(res, safe_extra)

            if caps.missing_capabilities:
                logger.info(
                    "schema_degraded debate_id=%s missing=%s",
                    debate.id, caps.missing_capabilities,
                )
        else:
            logger.warning("schema_capabilities_failed debate_id=%s — skipping enrichment", debate.id)

    return res


def serialize_debate_base(debate) -> dict:
    """Serialize fields that live directly on the Debate object.

    Safe to call without session — does not query auxiliary tables.
    """
    config = debate.config or {}
    return {
        "id": debate.id,
        "prompt": debate.prompt,
        "status": debate.status,
        "mode": getattr(debate, "mode", "arena"),
        "created_at": debate.created_at,
        "updated_at": debate.updated_at,
        "final_content": debate.final_content,
        "model_id": debate.model_id,
        "routed_model": debate.routed_model,
        "routing_policy": debate.routing_policy,
        "config": config,
        "panel_config": debate.panel_config,
        "routing_meta": debate.routing_meta,
        "final_meta": debate.final_meta,
        "engine_version": debate.engine_version,
        "user_id": debate.user_id,
        "team_id": debate.team_id,
        "runner_id": debate.runner_id,
        "run_attempt": getattr(debate, "run_attempt", 0),
    }


def _detect_read_quality(extra: dict) -> str:
    """Derive a human-readable quality indicator from extra fields."""
    if extra.get("continuation_status") is not None or extra.get("stage_checkpoints") is not None:
        return "full"
    return "degraded"


def serialize_debate_public(debate, continuation_status: Optional[str] = None, session=None) -> dict:
    """
    Serialize a Debate ORM object into a public-safe dictionary.

    Used for unauthenticated access to public runs.
    """
    final_meta = debate.final_meta or {}
    safe_meta = _safe_final_meta(final_meta)
    extra = _get_debate_extra_fields(debate, session=session, continuation_status=continuation_status)
    query_failures = _get_query_failures(extra)
    read_quality = _detect_read_quality(extra)
    if query_failures:
        read_quality = "degraded"

    return PublicDebateDTO(
        id=debate.id,
        prompt=debate.prompt,
        status=debate.status,
        mode=getattr(debate, "mode", "arena"),
        created_at=debate.created_at,
        updated_at=debate.updated_at,
        final_content=debate.final_content,
        is_public=True,
        model_id=debate.model_id,
        routed_model=debate.routed_model,
        continuation_status=extra["continuation_status"],
        successful_count=safe_meta.get("successful_count"),
        total_count=safe_meta.get("total_count"),
        synthesis_success=safe_meta.get("synthesis_success"),
        models=safe_meta.get("models"),
        synthesis_report=safe_meta.get("synthesis_report"),
        synthesis_status=safe_meta.get("synthesis_status"),
        synthesis_error=None,
        fallback_model=safe_meta.get("fallback_model"),
        fallback_reason=safe_meta.get("fallback_reason"),
        fallback_response=None,
        semantic_analysis=safe_meta.get("semantic_analysis"),
        divergence_breakdown=safe_meta.get("divergence_breakdown"),
        current_stage=extra["current_stage"],
        stage_checkpoints=extra["stage_checkpoints"],
        continuation_id=extra["continuation_id"],
        perspectives_ready_at=extra["perspectives_ready_at"],
        responses_received=extra["responses_received"],
        models_expected=extra["models_expected"],
        scores_received=extra["scores_received"],
        verification_status=extra["verification_status"],
        read_quality=read_quality,
        query_failures=query_failures,
    ).model_dump()



def _get_missing_capabilities(debate, extra: dict) -> list[str]:
    """Detect genuinely missing schema capabilities, not just empty result sets.

    A Debate with zero rows in a table is a valid empty result, not a missing
    capability. Only query failures or schema absence count as missing.
    """
    missing = []
    if extra.get("stage_checkpoints") is None and extra.get("_checkpoint_query_failed"):
        missing.append("stage_checkpoints")
    if extra.get("continuation_id") is None and extra.get("_continuation_query_failed"):
        missing.append("continuations")
    if extra.get("responses_received") is None and extra.get("_message_query_failed"):
        missing.append("message_counts")
    if extra.get("scores_received") is None and extra.get("_score_query_failed"):
        missing.append("score_counts")
    return missing


def _get_query_failures(extra: dict) -> list[str]:
    """Return names of enrichment queries that failed at runtime."""
    failures = []
    if extra.get("_checkpoint_query_failed"):
        failures.append("checkpoints")
    if extra.get("_continuation_query_failed"):
        failures.append("continuations")
    if extra.get("_message_query_failed"):
        failures.append("message_counts")
    if extra.get("_score_query_failed"):
        failures.append("score_counts")
    return failures


def serialize_debate_private(debate, continuation_status: Optional[str] = None, session=None) -> dict:
    """
    Serialize a Debate ORM object into a full private dictionary.

    Used for authenticated owner/admin access.
    """
    config = debate.config or {}
    extra = _get_debate_extra_fields(debate, session=session, continuation_status=continuation_status)
    missing_capabilities = _get_missing_capabilities(debate, extra)
    query_failures = _get_query_failures(extra)
    read_quality = "degraded" if (missing_capabilities or query_failures) else "full"

    # P143: Extract safe synthesis fields for top-level mirroring
    safe_meta = _safe_final_meta(debate.final_meta)

    return PrivateDebateDTO(
        id=debate.id,
        prompt=debate.prompt,
        status=debate.status,
        mode=getattr(debate, "mode", "arena"),
        created_at=debate.created_at,
        updated_at=debate.updated_at,
        final_content=debate.final_content,
        is_public=config.get("is_public", False),
        model_id=debate.model_id,
        routed_model=debate.routed_model,
        routing_policy=debate.routing_policy,
        continuation_status=extra["continuation_status"],
        config=config,
        panel_config=debate.panel_config,
        routing_meta=debate.routing_meta,
        final_meta=debate.final_meta,
        engine_version=debate.engine_version,
        # P143: Top-level synthesis aliases (same fields PublicDebateDTO exposes)
        synthesis_report=safe_meta.get("synthesis_report"),
        synthesis_status=safe_meta.get("synthesis_status"),
        synthesis_error=safe_meta.get("synthesis_error"),
        synthesis_success=safe_meta.get("synthesis_success"),
        fallback_model=safe_meta.get("fallback_model"),
        fallback_reason=safe_meta.get("fallback_reason"),
        fallback_response=safe_meta.get("fallback_response"),
        semantic_analysis=safe_meta.get("semantic_analysis"),
        divergence_breakdown=safe_meta.get("divergence_breakdown"),
        successful_count=safe_meta.get("successful_count"),
        total_count=safe_meta.get("total_count"),
        models=safe_meta.get("models"),
        user_id=debate.user_id,
        team_id=debate.team_id,
        runner_id=debate.runner_id,
        run_attempt=getattr(debate, "run_attempt", 0),
        current_stage=extra["current_stage"],
        stage_checkpoints=extra["stage_checkpoints"],
        continuation_id=extra["continuation_id"],
        perspectives_ready_at=extra["perspectives_ready_at"],
        responses_received=extra["responses_received"],
        models_expected=extra["models_expected"],
        scores_received=extra["scores_received"],
        verification_status=extra["verification_status"],
        read_quality=read_quality,
        missing_capabilities=missing_capabilities,
        query_failures=query_failures,
    ).model_dump()


# ---------------------------------------------------------------------------
# Event serialization
# ---------------------------------------------------------------------------

# Fields that are safe for public event serialization
_PUBLIC_EVENT_SAFE_FIELDS = {
    "type", "round", "display_name", "provider", "content", "text",
    "logo_url", "persona_type", "persona_tagline", "success", "mode", "at",
    "persona", "judge", "score", "rationale", "role", "actor",
    "candidate_a", "candidate_b", "winner", "loser", "judge_id",
    "model_id",  # Safe public model ID (not internal)
}

# Fields to explicitly exclude from public events
_PUBLIC_EVENT_EXCLUDE_FIELDS = {
    "seat_id",       # Internal seat identifier
    "seat_name",     # Redundant with display_name
    "meta",          # Raw internal metadata
    "user_id",       # Owner identity
    "team_id",       # Team identity
    "debug",         # Debug info
    "error_details", # Internal error details
    "config",        # Config internals
}


def serialize_event_public(event: dict) -> dict:
    """
    Filter a single event dict to only include public-safe fields.

    Removes internal metadata like seat_id, raw meta, user/team IDs.
    """
    safe = {}
    for key, value in event.items():
        if key in _PUBLIC_EVENT_EXCLUDE_FIELDS:
            continue
        if key in _PUBLIC_EVENT_SAFE_FIELDS:
            safe[key] = value
    return safe


def serialize_events_public(events: list[dict]) -> list[dict]:
    """Filter a list of event dicts to public-safe representation."""
    return [serialize_event_public(e) for e in events]
