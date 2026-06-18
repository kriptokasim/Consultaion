from __future__ import annotations

from auth import get_current_admin
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Request
from models import User
from sqlmodel import Session

router = APIRouter()


@router.get("/providers/health")
def admin_providers_health(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Get the health and configuration status of all LLM providers.
    """
    from config import settings
    # List of all provider IDs we support
    providers = [
        "openai",
        "anthropic",
        "gemini",
        "groq",
        "deepinfra",
        "together",
        "fireworks",
        "mistral",
        "xai",
        "perplexity",
        "openrouter",
    ]
    
    health = {}
    for p in providers:
        # Determine active / key status
        if p == "gemini":
            has_key = bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
        else:
            has_key = bool(getattr(settings, f"{p.upper()}_API_KEY", None))
            
        health[p] = {
            "status": "active" if has_key else "missing_key",
            "has_key": has_key,
        }
        
    return {
        "status": "ok",
        "providers": health
    }


@router.post("/providers/{provider}/test")
async def admin_test_provider(
    provider: str,
    req: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Perform a low-latency diagnostic completion ping to verify the API key for a provider is valid.
    """
    from config import settings
    
    # 1. Resolve provider configuration
    provider = provider.lower()
    
    fast_models = {
        "openai": "openai/gpt-4o-mini",
        "anthropic": "anthropic/claude-3-haiku-20240307",
        "gemini": "gemini/gemini-2.0-flash",
        "groq": "groq/llama-3.3-70b-versatile",
        "deepinfra": "deepinfra/meta-llama/Llama-3.3-70B-Instruct",
        "together": "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "fireworks": "fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct",
        "mistral": "mistral/mistral-large-latest",
        "xai": "xai/grok-2",
        "perplexity": "perplexity/sonar-reasoning",
        "openrouter": "openrouter/openai/gpt-4o-mini",
    }
    
    if provider not in fast_models:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider or no diagnostic model defined for '{provider}'"
        )
        
    # Check if key exists
    if provider == "gemini":
        has_key = bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
    else:
        has_key = bool(getattr(settings, f"{provider.upper()}_API_KEY", None))
        
    if not has_key:
        return {
            "success": False,
            "error": "API key is not configured in settings",
            "latency_ms": 0,
        }
        
    # Ensure keys are exported to os.environ for LiteLLM
    from model_gateway import export_api_keys
    export_api_keys()
    
    model_to_test = fast_models[provider]
    
    import time
    from litellm import acompletion
    
    start_ts = time.monotonic()
    try:
        # Perform low-latency ping completion
        response = await acompletion(
            model=model_to_test,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        latency_ms = (time.monotonic() - start_ts) * 1000
        
        # Extract content
        content = response.choices[0].message["content"] if response.choices else ""
        
        # Create audit log
        from audit import record_audit
        record_audit(
            f"test_provider_{provider}",
            user_id=admin.id,
            target_type="provider",
            target_id=provider,
            meta={"success": True, "latency_ms": latency_ms, "model": model_to_test},
            ip_address=req.client.host if req.client else None,
            session=session,
        )
        
        return {
            "success": True,
            "model_tested": model_to_test,
            "response": content.strip(),
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        latency_ms = (time.monotonic() - start_ts) * 1000
        
        # Create audit log
        from audit import record_audit
        record_audit(
            f"test_provider_{provider}",
            user_id=admin.id,
            target_type="provider",
            target_id=provider,
            meta={"success": False, "error": str(e), "model": model_to_test},
            ip_address=req.client.host if req.client else None,
            session=session,
        )
        
        return {
            "success": False,
            "model_tested": model_to_test,
            "error": str(e),
            "latency_ms": round(latency_ms, 2),
        }
