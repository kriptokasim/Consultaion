"""
Public-safe and private DTO serializers for the Debate model.

Prevents internal field leakage to unauthenticated public users while
preserving full data for owners and admins.

Security principle: Public access means read-only access to a safe public
representation, not full access to the internal Debate object.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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

    # Safe subset of final_meta
    successful_count: Optional[int] = None
    total_count: Optional[int] = None
    synthesis_success: Optional[bool] = None
    models: Optional[List[Dict[str, Any]]] = None


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

    # Full metadata for owners
    config: Optional[Dict[str, Any]] = None
    panel_config: Optional[Dict[str, Any]] = None
    routing_meta: Optional[Dict[str, Any]] = None
    final_meta: Optional[Dict[str, Any]] = None
    engine_version: Optional[str] = None

    # Ownership
    user_id: Optional[str] = None
    team_id: Optional[str] = None

    # Worker internals (admin/owner diagnostics)
    runner_id: Optional[str] = None
    run_attempt: int = 0


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
    for key in ("successful_count", "total_count", "synthesis_success", "models"):
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


def serialize_debate_public(debate) -> dict:
    """
    Serialize a Debate ORM object into a public-safe dictionary.

    Used for unauthenticated access to public runs.
    """
    config = debate.config or {}
    final_meta = debate.final_meta or {}
    safe_meta = _safe_final_meta(final_meta)

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
        successful_count=safe_meta.get("successful_count"),
        total_count=safe_meta.get("total_count"),
        synthesis_success=safe_meta.get("synthesis_success"),
        models=safe_meta.get("models"),
    ).model_dump()


def serialize_debate_private(debate) -> dict:
    """
    Serialize a Debate ORM object into a full private dictionary.

    Used for authenticated owner/admin access.
    """
    config = debate.config or {}

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
        config=config,
        panel_config=debate.panel_config,
        routing_meta=debate.routing_meta,
        final_meta=debate.final_meta,
        engine_version=debate.engine_version,
        user_id=debate.user_id,
        team_id=debate.team_id,
        runner_id=debate.runner_id,
        run_attempt=getattr(debate, "run_attempt", 0),
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
