from __future__ import annotations

from typing import Any

from checks import check_db_readiness, check_sse_readiness
from config import settings
from fastapi import APIRouter, Response, status

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """
    Liveness probe.
    
    Always 200 if the app process is running and accepting requests.
    Used by load balancers to determine if the pod is alive.
    """
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """
    Readiness probe.
    
    Returns 503 if critical dependencies (DB, SSE) are not ready.
    Used by k8s/deployments to know when to send traffic.
    """
    db_ok, db_info = check_db_readiness()
    sse_ok, sse_info = await check_sse_readiness()
    
    status_code = status.HTTP_200_OK
    if not db_ok or not sse_ok:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    response.status_code = status_code
    return {
        "status": "ready" if status_code == 200 else "not_ready",
        "details": {
            "db": db_info,
            "sse": sse_info,
        },
        "meta": {
            "env": settings.ENV,
            "version": settings.APP_VERSION,
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
