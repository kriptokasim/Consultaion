from __future__ import annotations

import os
import time
import json
import logging
from typing import Any, Dict, List, Optional

from checks import check_db_readiness, check_sse_readiness
from config import settings
from fastapi import APIRouter, Response, status, Depends, HTTPException, Request
from sqlmodel import Session, select, func

from database import get_session
from auth import get_current_admin
from models import User, Debate, Message, Score, DebateCheckpoint, DebateStageCheckpoint, LLMUsageLog
from litellm import acompletion
from ratelimit import increment_ip_bucket, record_429

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


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """
    Readiness probe.
    
    Returns 503 if critical dependencies (DB, SSE) are not ready.
    Used by k8s/deployments to know when to send traffic.
    """
    db_ok, db_info = check_db_readiness()
    sse_ok, sse_info = await check_sse_readiness()
    
    schema_info = {"status": "unknown"}
    try:
        from database import SessionLocal
        from services.schema_capabilities import get_registry, get_schema_capabilities
        with SessionLocal() as session:
            caps = get_schema_capabilities(session, get_registry())
            schema_info = {
                "at_head": caps.is_at_alembic_head,
                "missing_capabilities": caps.missing_capabilities,
            }
            if not caps.is_at_alembic_head:
                schema_info["status"] = "behind_head"
                db_ok = False
            else:
                schema_info["status"] = "ok"
    except Exception as exc:
        schema_info["status"] = "error"
        schema_info["error"] = str(exc)
        db_ok = False
    
    status_code = status.HTTP_200_OK
    if not db_ok or not sse_ok:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    response.status_code = status_code
    return {
        "status": "ready" if status_code == 200 else "not_ready",
        "details": {
            "db": db_info,
            "sse": sse_info,
            "schema": schema_info,
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
    
    Returns status of AI providers based on configured API keys.
    Used by frontend to display provider degradation warnings.
    """
    providers = []
    
    # Check each provider based on configured keys
    provider_configs = [
        ("openai", settings.OPENAI_API_KEY),
        ("anthropic", settings.ANTHROPIC_API_KEY),
        ("gemini", settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY),
        ("openrouter", settings.OPENROUTER_API_KEY),
        ("groq", settings.GROQ_API_KEY),
        ("mistral", settings.MISTRAL_API_KEY),
    ]
    
    for provider_name, api_key in provider_configs:
        if api_key:
            # Provider is configured - assume healthy
            # In production, you could ping provider endpoints
            providers.append({
                "provider": provider_name,
                "status": "healthy",
            })
    
    return {"providers": providers}


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """
    Detailed API status endpoint.
    
    Returns the configuration and operational status of database, SSE, 
    and SOTA AI model providers (OpenAI, Anthropic, Gemini, OpenRouter).
    Used by the public status page.
    """
    db_ok, _ = check_db_readiness()
    sse_ok, _ = await check_sse_readiness()
    
    providers = {
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
            "status": "operational" if settings.OPENAI_API_KEY else "not_configured"
        },
        "anthropic": {
            "configured": bool(settings.ANTHROPIC_API_KEY),
            "status": "operational" if settings.ANTHROPIC_API_KEY else "not_configured"
        },
        "gemini": {
            "configured": bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY),
            "status": "operational" if (settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY) else "not_configured"
        },
        "openrouter": {
            "configured": bool(settings.OPENROUTER_API_KEY),
            "status": "operational" if settings.OPENROUTER_API_KEY else "not_configured"
        }
    }
    
    # If any critical system or SOTA provider is down, we mark as degraded
    overall_status = "operational"
    if not db_ok or not sse_ok:
        overall_status = "major_outage"
    elif not all(p["configured"] for p in providers.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "database": "operational" if db_ok else "down",
        "sse": "operational" if sse_ok else "down",
        "providers": providers,
        "version": settings.APP_VERSION,
        "env": settings.ENV
    }


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
    from model_gateway.provider_health import get_redis, get_status_key, get_failures_key
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

    response_count = session.exec(
        select(func.count(Message.id)).where(
            Message.debate_id == debate_id,
            Message.role == "arena_response"
        )
    ).one()

    score_count = session.exec(
        select(func.count(Score.id)).where(Score.debate_id == debate_id)
    ).one()

    checkpoint_count = session.exec(
        select(func.count(DebateCheckpoint.id)).where(DebateCheckpoint.debate_id == debate_id)
    ).one()

    stage_checkpoint_count = session.exec(
        select(func.count(DebateStageCheckpoint.id)).where(DebateStageCheckpoint.debate_id == debate_id)
    ).one()

    # 3. Query provider failures from LLMUsageLog
    failures_query = select(LLMUsageLog).where(
        LLMUsageLog.debate_id == debate_id,
        LLMUsageLog.success == False
    ).order_by(LLMUsageLog.created_at.desc())
    failed_logs = session.exec(failures_query).all()

    provider_failures = []
    for log in failed_logs:
        provider_failures.append({
            "provider": log.provider,
            "model": log.model,
            "role": log.role,
            "error_message": log.error_message,
            "timestamp": log.created_at.isoformat() if log.created_at else None
        })

    # Group counts of failures by provider/model
    failures_summary = {}
    for log in failed_logs:
        key = f"{log.provider}/{log.model}"
        failures_summary[key] = failures_summary.get(key, 0) + 1

    # 4. Schema revision check
    db_ok, db_info = check_db_readiness()
    
    # 5. Build response without credentials, prompts, or user emails
    return {
        "debate_id": debate.id,
        "status": debate.status,
        "mode": debate.mode,
        "created_at": debate.created_at.isoformat() if debate.created_at else None,
        "updated_at": debate.updated_at.isoformat() if debate.updated_at else None,
        "counts": {
            "messages": message_count,
            "arena_responses": response_count,
            "scores": score_count,
            "checkpoints": checkpoint_count,
            "stage_checkpoints": stage_checkpoint_count,
        },
        "failures": {
            "total": len(failed_logs),
            "summary": failures_summary,
            "details": provider_failures[:10]
        },
        "schema": {
            "ok": db_ok,
            "current_revision": db_info.get("revision", {}).get("current"),
            "head_revision": db_info.get("revision", {}).get("head"),
        },
        "meta": {
            "app_version": settings.APP_VERSION,
            "env": settings.ENV,
            "git_sha": _GIT_SHA,
            "build_timestamp": _BUILD_TIMESTAMP,
        }
    }


@router.get("/ops/providers/readiness")
async def get_providers_readiness(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    Get readiness, circuit state, and diagnostic info for all model providers,
    plus worker node heartbeats.
    Admin-only.
    """
    providers = ["openai", "anthropic", "gemini", "openrouter", "groq", "mistral"]
    provider_results = {}
    
    # Check each provider
    for provider in providers:
        # 1. Configuration Check
        if provider == "openai":
            configured = bool(settings.OPENAI_API_KEY)
        elif provider == "anthropic":
            configured = bool(settings.ANTHROPIC_API_KEY)
        elif provider == "gemini":
            configured = bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
        elif provider == "openrouter":
            configured = bool(settings.OPENROUTER_API_KEY)
        elif provider == "groq":
            configured = bool(settings.GROQ_API_KEY)
        elif provider == "mistral":
            configured = bool(settings.MISTRAL_API_KEY)
        else:
            configured = False
            
        # 2. Circuit Breaker status from Redis
        circuit = get_provider_circuit_status(provider)
        
        # 3. Last failure from DB
        last_fail_query = select(LLMUsageLog).where(
            LLMUsageLog.provider == provider,
            LLMUsageLog.success == False
        ).order_by(LLMUsageLog.created_at.desc())
        last_fail = session.exec(last_fail_query).first()
        
        last_failure_info = None
        if last_fail:
            last_failure_info = {
                "timestamp": last_fail.created_at.isoformat() if last_fail.created_at else None,
                "model": last_fail.model,
                "error_message": last_fail.error_message
            }
            
        provider_results[provider] = {
            "configured": configured,
            "circuit_state": circuit["state"],
            "consecutive_failures": circuit["consecutive_failures"],
            "circuit_ttl_seconds": circuit["ttl"],
            "last_failure": last_failure_info
        }
        
    # 4. Worker Heartbeats
    workers = get_active_workers()
    
    return {
        "providers": provider_results,
        "workers": workers,
        "meta": {
            "app_version": settings.APP_VERSION,
            "env": settings.ENV,
            "git_sha": _GIT_SHA,
            "build_timestamp": _BUILD_TIMESTAMP,
        }
    }


@router.post("/ops/providers/{provider}/probe")
async def probe_provider(
    provider: str,
    request: Request,
    current_admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    """
    Perform a minimal cost test call to check model provider health/latency.
    Admin-only.
    """
    # 1. Validate provider
    providers_map = {
        "openai": "openai/gpt-4o-mini",
        "anthropic": "anthropic/claude-3-haiku-20240307",
        "gemini": "gemini/gemini-2.0-flash",
        "openrouter": "openrouter/openai/gpt-4o-mini",
        "groq": "groq/llama-3.3-70b-versatile",
        "mistral": "mistral/mistral-large-latest"
    }
    
    if provider not in providers_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' is not supported or not probeable."
        )
        
    # 2. IP Rate Limit Check (5 requests per minute per IP/user)
    ip = request.client.host if request.client else "anonymous"
    user_id = current_admin.id if current_admin else None
    
    allowed, retry_after = increment_ip_bucket(
        ip, 
        window_seconds=60, 
        max_requests=5, 
        user_id=user_id
    )
    if not allowed:
        record_429(ip, request.url.path)
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded for provider probe. Limit: 5 calls/min.",
                "code": "rate_limit.exceeded",
                "retry_after_seconds": retry_after
            }
        )
        
    target_model = providers_map[provider]
    start_ts = time.monotonic()
    
    try:
        response = await acompletion(
            model=target_model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=5,
        )
        latency_ms = (time.monotonic() - start_ts) * 1000
        content = response.choices[0].message.get("content") or ""
        return {
            "status": "success",
            "provider": provider,
            "model_used": target_model,
            "latency_ms": round(latency_ms, 2),
            "response": content.strip()
        }
    except Exception as e:
        latency_ms = (time.monotonic() - start_ts) * 1000
        from llm_errors import classify_provider_exception
        failure = classify_provider_exception(e)
        return {
            "status": "failed",
            "provider": provider,
            "model_used": target_model,
            "latency_ms": round(latency_ms, 2),
            "error_code": failure.code.value,
            "error_message": failure.message,
        }


