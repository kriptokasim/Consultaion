from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from auth import get_current_admin, get_current_user
from checks import check_db_readiness, check_model_registry_readiness, check_sse_readiness

# CORE-AUDIT (CE-2): sync DB/alembic checks block the event loop when run
# directly inside async routes. Offload to the default executor so slow DB
# readiness probes cannot freeze the whole worker (incl. /healthz).
async def _db_readiness_async() -> tuple[bool, dict[str, Any]]:
    return await asyncio.get_running_loop().run_in_executor(None, check_db_readiness)
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from litellm import acompletion
from models import (
    Debate,
    DebateCheckpoint,
    DebateStageCheckpoint,
    LLMUsageLog,
    Message,
    Score,
    User,
)
from ratelimit import increment_ip_bucket, record_429
from sqlmodel import Session, func, select

from config import settings

router = APIRouter(tags=["ops"])

_GIT_SHA = os.environ.get("GIT_SHA", "unknown")
_BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "unknown")
logger = logging.getLogger("ops")



@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """
    Liveness probe.
    
    Always 200 if the app process is running and accepting requests.
    Used by load balancers to determine if the pod is alive.
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "git_sha": _GIT_SHA,
        "build_timestamp": _BUILD_TIMESTAMP,
    }


def _probe_error_category(error: str) -> str:
    """Classify a probe failure without echoing the raw exception text.

    /readyz is unauthenticated and raw driver errors carry the DSN — host,
    port and username — so only the category crosses the boundary.
    """
    lowered = error.lower()
    if "pending migrations" in lowered:
        return "pending_migrations"
    if "schema integrity" in lowered:
        return "schema_integrity_failed"
    if "ping failed" in lowered:
        return "backend_ping_failed"
    if "no models enabled" in lowered:
        return "no_models_enabled"
    return "dependency_unavailable"


def _sanitize_probe_info(probe: str, info: dict[str, Any]) -> dict[str, Any]:
    """Log the full probe error server-side, expose only its category."""
    error = info.get("error")
    if not error:
        return info
    logger.error("readiness_probe_failed probe=%s error=%s", probe, error)
    sanitized = dict(info)
    sanitized["error"] = _probe_error_category(str(error))
    return sanitized


def _schema_readiness() -> dict[str, Any]:
    """Reflect schema capabilities. Blocking — call via the default executor."""
    from database import SessionLocal
    from services.schema_capabilities import get_registry, get_schema_capabilities

    with SessionLocal() as session:
        caps = get_schema_capabilities(session, get_registry())
        return {
            "status": "ok" if caps.is_at_alembic_head else "behind_head",
            "at_head": caps.is_at_alembic_head,
            "missing_capabilities": caps.missing_capabilities,
        }


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """
    Readiness probe.

    Returns 503 if critical dependencies (DB, SSE) are not ready.
    Used by k8s/deployments to know when to send traffic.
    """
    db_ok, db_info = await _db_readiness_async()
    sse_ok, sse_info = await check_sse_readiness()
    registry_ok, registry_info = check_model_registry_readiness()

    schema_info: dict[str, Any] = {"status": "unknown"}
    if settings.ENV == "test":
        schema_info["status"] = "test_bypass"
    else:
        try:
            schema_info = await asyncio.get_running_loop().run_in_executor(
                None, _schema_readiness
            )
            if not schema_info["at_head"]:
                db_ok = False
        except Exception as exc:
            logger.error("readiness_probe_failed probe=schema error=%s", exc)
            schema_info = {
                "status": "error",
                "error": _probe_error_category(str(exc)),
            }
            db_ok = False

    status_code = status.HTTP_200_OK
    if not db_ok or not sse_ok or not registry_ok:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    response.status_code = status_code
    return {
        "status": "ready" if status_code == 200 else "not_ready",
        "details": {
            "db": _sanitize_probe_info("db", db_info),
            "sse": _sanitize_probe_info("sse", sse_info),
            "schema": schema_info,
            "models": _sanitize_probe_info("models", registry_info),
        },
        "meta": {
            "env": settings.ENV,
            "version": settings.APP_VERSION,
            "git_sha": _GIT_SHA,
            "build_timestamp": _BUILD_TIMESTAMP,
        }
    }


@router.get("/api/health/providers")
async def provider_health() -> dict[str, Any]:
    """
    Provider health check.

    Uses the same breaker-backed health contract as /api/status so callers
    cannot be told that a provider is healthy merely because an API key exists.
    """
    configured_providers = (
        ("openai", bool(settings.OPENAI_API_KEY)),
        ("anthropic", bool(settings.ANTHROPIC_API_KEY)),
        ("gemini", bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)),
        ("openrouter", bool(settings.OPENROUTER_API_KEY)),
        ("groq", bool(settings.GROQ_API_KEY)),
        ("mistral", bool(settings.MISTRAL_API_KEY)),
    )
    entries = await asyncio.gather(
        *(
            asyncio.to_thread(_provider_status, provider, configured)
            for provider, configured in configured_providers
        )
    )
    return {
        "providers": [
            {
                "provider": provider,
                **entry,
                # Preserve the legacy frontend token for healthy providers.
                "status": "healthy" if entry["status"] == "operational" else entry["status"],
            }
            for (provider, _), entry in zip(configured_providers, entries, strict=True)
            if entry["status"] != "not_configured"
        ]
    }



def _provider_status(provider: str, configured: bool) -> dict[str, Any]:
    """Real health for one provider, not merely "an env var is set".

    This endpoint used to report `operational` whenever a key string was
    non-empty. It never called the provider, never checked credit, and never
    looked at the circuit breaker -- so on 2026-09-07, with OpenAI returning
    credit_balance_exhausted, Anthropic insufficient_balance and Gemini
    invalid_credentials (all three tripping the global circuit), the public
    status page showed "All Systems Operational". An invalid key is still a
    non-empty string.

    get_provider_circuit_status() already had the answer and simply was not
    called from here. The gateway trips that breaker on terminal provider
    failures, which is exactly the signal a status page exists to surface.
    """
    if not configured:
        return {"configured": False, "status": "not_configured"}

    circuit = get_provider_circuit_status(provider)
    failures = int(circuit.get("consecutive_failures") or 0)

    if not circuit.get("redis_connected", True):
        # A failed breaker read is not evidence of provider health. Do not
        # report "operational" while the health source itself is unavailable.
        status = "unverified"
    elif circuit.get("state") == "open":
        status = "outage"
    elif failures > 0:
        # Failing but not yet tripped: visible before it becomes an outage,
        # which is the window where a status page is actually worth having.
        status = "degraded"
    else:
        status = "operational"

    entry: dict[str, Any] = {
        "configured": True,
        "status": status,
        "consecutive_failures": failures,
    }
    if circuit.get("ttl") is not None:
        entry["retry_in_seconds"] = circuit["ttl"]
    if not circuit.get("redis_connected", True):
        # Be honest that the breaker state could not be read, rather than
        # letting "closed by default" masquerade as a healthy check.
        entry["health_source"] = "unverified"
    return entry


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """
    Detailed API status endpoint.
    
    Returns the configuration and operational status of database, SSE, 
    and SOTA AI model providers (OpenAI, Anthropic, Gemini, OpenRouter).
    Used by the public status page.
    """
    db_ok, _ = await _db_readiness_async()
    sse_ok, _ = await check_sse_readiness()

    configured_providers = (
        ("openai", bool(settings.OPENAI_API_KEY)),
        ("anthropic", bool(settings.ANTHROPIC_API_KEY)),
        ("gemini", bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)),
        ("openrouter", bool(settings.OPENROUTER_API_KEY)),
    )
    # get_provider_circuit_status() is synchronous (Redis). Running all four
    # checks in worker threads keeps /api/status from blocking the FastAPI
    # event loop during a Redis stall.
    provider_entries = await asyncio.gather(
        *(
            asyncio.to_thread(_provider_status, provider, configured)
            for provider, configured in configured_providers
        )
    )
    providers = {
        provider: entry
        for (provider, _), entry in zip(configured_providers, provider_entries, strict=True)
    }

    overall_status = "operational"
    if not db_ok or not sse_ok:
        overall_status = "major_outage"
    elif all(p["status"] in ("outage", "not_configured", "unverified") for p in providers.values()):
        # Nothing verifiably usable is left to serve a debate with.
        overall_status = "major_outage"
    elif any(p["status"] in ("outage", "degraded", "not_configured", "unverified") for p in providers.values()):
        overall_status = "degraded"

    payload = {
        "status": overall_status,
        "database": "operational" if db_ok else "down",
        "sse": "operational" if sse_ok else "down",
        "providers": providers,
        "version": settings.APP_VERSION,
        "env": settings.ENV,
    }

    # Free-only mode means the SOTA providers are not serving debates at all,
    # whatever their keys say. Reporting them without this reads as a healthy
    # frontier roster when nothing frontier is actually reachable.
    if getattr(settings, "FREE_ONLY_MODE", False):
        payload["free_only_mode"] = True

    return payload


@router.get("/meta/contracts")
async def get_contracts() -> dict[str, Any]:
    return {
        "git_sha": _GIT_SHA,
        "contracts": {
            "debate_detail": 2,
            "persisted_responses": settings.RESPONSES_CONTRACT_VERSION,
            "timeline": 1,
            "stream_events": 1,
        },
    }


def get_active_workers() -> list[dict[str, Any]]:
    from redis_pool import get_sync_redis_client
    redis_client = get_sync_redis_client()
    if not redis_client:
        return []
    
    workers = []
    try:
        keys = redis_client.keys("worker:heartbeat:*")
        for key in keys:
            val = redis_client.get(key)
            if val:
                try:
                    data = json.loads(val)
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    worker_name = key_str.replace("worker:heartbeat:", "")
                    
                    last_seen = data.get("timestamp", 0)
                    age = time.time() - last_seen
                    
                    workers.append({
                        "name": worker_name,
                        "git_sha": data.get("git_sha", "unknown"),
                        "age_seconds": round(age, 2),
                        "status": "healthy" if age < 30 else "stale"
                    })
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Error scanning worker heartbeats: {e}")
    return workers


def get_provider_circuit_status(provider: str) -> dict[str, Any]:
    from model_gateway.provider_health import get_failures_key, get_redis, get_status_key
    redis_client = get_redis()
    if not redis_client:
        return {
            "state": "closed",
            "consecutive_failures": 0,
            "ttl": None,
            "redis_connected": False
        }
    try:
        status_val = redis_client.get(get_status_key(provider))
        failures_val = redis_client.get(get_failures_key(provider))
        
        status_str = status_val.decode("utf-8") if isinstance(status_val, bytes) else status_val
        state = "open" if status_str == "open" else "closed"
        
        consecutive_failures = 0
        if failures_val:
            consecutive_failures = int(failures_val)
            
        ttl = None
        if state == "open":
            ttl = redis_client.ttl(get_status_key(provider))
            if ttl is not None and ttl < 0:
                ttl = None
                
        return {
            "state": state,
            "consecutive_failures": consecutive_failures,
            "ttl": ttl,
            "redis_connected": True
        }
    except Exception:
        return {
            "state": "closed",
            "consecutive_failures": 0,
            "ttl": None,
            "redis_connected": False
        }


@router.get("/ops/runtime-parity")
async def get_runtime_parity(
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """Compare API git_sha against all active worker heartbeats."""
    from redis_pool import get_sync_redis_client
    redis_client = get_sync_redis_client()
    workers = []
    all_match = True

    if redis_client:
        try:
            keys = redis_client.keys("worker:heartbeat:*")
            for key in keys:
                val = redis_client.get(key)
                if val:
                    try:
                        data = json.loads(val)
                        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                        worker_name = key_str.replace("worker:heartbeat:", "")
                        last_seen = data.get("timestamp", 0)
                        age = time.time() - last_seen

                        worker_sha = data.get("git_sha", "unknown")
                        if worker_sha != _GIT_SHA:
                            all_match = False

                        workers.append({
                            "name": worker_name,
                            "git_sha": worker_sha,
                            "last_seen": last_seen,
                            "age_seconds": round(age, 2),
                            "queue_names": data.get("queue_names", []),
                            "status": "healthy" if age < 30 else "stale",
                        })
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Error scanning worker heartbeats for parity: %s", e)

    return {
        "api_git_sha": _GIT_SHA,
        "workers": workers,
        "parity": all_match,
    }


@router.get("/ops/debates/{debate_id}/diagnostics")
async def get_debate_diagnostics(
    debate_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    Get detailed diagnostics for a debate run.
    Admin-only.
    """
    # 1. Fetch debate
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found."
        )

    # 2. Get database counts
    message_count = session.exec(
        select(func.count(Message.id)).where(Message.debate_id == debate_id)
    ).one()