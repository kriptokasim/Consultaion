"""Transport seam that routes gateway calls through a LiteLLM proxy service.

The gateway already speaks LiteLLM as an in-process SDK. The proxy is the same
protocol reached over HTTP, so switching backends is a transport concern rather
than a new adapter: resolve the deployment name the proxy publishes, then hand
``acompletion`` an ``api_base`` and a virtual key.

Everything the proxy adds over the SDK -- per-user virtual keys with budgets, a
global spend ceiling, per-deployment cooldowns, cross-provider fallback -- lives
on the proxy side. This module's only job is to point calls at it, and to stay
completely inert when ``MODEL_GATEWAY_BACKEND`` is not ``proxy``.

Rollback is a single setting: with the backend on ``direct`` the overrides are
empty dicts and every call path behaves exactly as it did before.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("model_gateway.proxy_transport")

# Deployment names published by the proxy (config/litellm_proxy.yaml). Keys are
# canonical MODEL_MAP keys; anything absent falls through to the resolved
# litellm slug, which the proxy also accepts as a pass-through deployment.
PROXY_DEPLOYMENT_NAMES: Dict[str, str] = {
    "openai_fast": "seat_openai_fast",
    "openai_premium": "seat_openai_premium",
    "anthropic_reasoning": "seat_anthropic",
    "gemini_general": "seat_google",
    "gemini_pro": "seat_google",
    "groq_fast": "seat_groq",
    "deepseek-r1": "seat_deepseek",
    "mistral_large": "seat_mistral",
    "xai_grok": "seat_xai",
    "router-smart": "seat_free_router",
    "router-deep": "seat_free_glm",
    "llama-3-free": "seat_free_gpt_oss",
    # Both spellings: the pools yaml and the arena registry use hyphens, the
    # free-model runtime addition uses underscores.
    "openrouter-nemotron-free": "seat_free_nemotron",
    "openrouter_nemotron_free": "seat_free_nemotron",
    "openrouter_glm_free": "seat_free_glm",
    "openrouter_gpt_oss_free": "seat_free_gpt_oss",
    "openrouter_fallback": "seat_free_router",
    "chair": "chair",
}


class ProxyConfigurationError(RuntimeError):
    """The proxy backend is selected but cannot be used safely."""


def _settings() -> Any:
    from config import settings

    return settings


def proxy_enabled() -> bool:
    """True when calls should be routed through the LiteLLM proxy service."""
    settings = _settings()
    backend = str(getattr(settings, "MODEL_GATEWAY_BACKEND", "direct") or "direct").strip().lower()
    if backend != "proxy":
        return False
    if not getattr(settings, "LITELLM_PROXY_URL", None):
        # Fail *open* onto the direct path rather than taking the product down
        # over a missing URL. The startup check below is what makes this loud.
        logger.error(
            "MODEL_GATEWAY_BACKEND=proxy but LITELLM_PROXY_URL is unset; "
            "falling back to direct provider calls for this request."
        )
        return False
    return True


def validate_proxy_configuration() -> None:
    """Fail closed at boot when the proxy backend is half-configured.

    Called from application startup. A missing URL or master key with the proxy
    backend selected is a deploy mistake, and discovering it on the first user
    debate is strictly worse than discovering it here.
    """
    settings = _settings()
    backend = str(getattr(settings, "MODEL_GATEWAY_BACKEND", "direct") or "direct").strip().lower()
    if backend not in {"direct", "proxy"}:
        raise ProxyConfigurationError(
            f"MODEL_GATEWAY_BACKEND must be 'direct' or 'proxy', got {backend!r}."
        )
    if backend != "proxy":
        return
    missing = [
        name
        for name in ("LITELLM_PROXY_URL", "LITELLM_PROXY_API_KEY")
        if not getattr(settings, name, None)
    ]
    if missing:
        raise ProxyConfigurationError(
            "MODEL_GATEWAY_BACKEND=proxy requires " + ", ".join(sorted(missing)) + "."
        )


def resolve_deployment(model_id: str, fallback_model: str) -> str:
    """Map a gateway model id onto the deployment name the proxy publishes.

    The proxy speaks the OpenAI protocol, so the model string it receives is a
    deployment name from its own ``model_list`` -- not a provider slug. Unknown
    ids pass the resolved slug straight through, which the proxy accepts via its
    wildcard deployment.
    """
    name = PROXY_DEPLOYMENT_NAMES.get(model_id)
    if name is None:
        try:
            from model_gateway.model_map import resolve_model_key

            name = PROXY_DEPLOYMENT_NAMES.get(resolve_model_key(model_id))
        except Exception:
            name = None
    if name is None:
        return fallback_model
    return f"openai/{name}"


def proxy_overrides(
    model_id: str,
    resolved_model: str,
    user_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Return acompletion kwargs that redirect one call through the proxy.

    Empty when the proxy backend is off, which is what keeps this a no-op on the
    direct path. A caller-supplied ``api_key`` always wins: BYOK users are
    calling their own provider account and must not be billed against the
    platform's virtual key.
    """
    if api_key:
        return {}
    if not proxy_enabled():
        return {}

    settings = _settings()
    virtual_key = _virtual_key_for(user_id)
    if not virtual_key:
        return {}

    return {
        "model": resolve_deployment(model_id, resolved_model),
        "api_base": str(settings.LITELLM_PROXY_URL).rstrip("/"),
        "api_key": virtual_key,
        "custom_llm_provider": "openai",
    }


def _virtual_key_for(user_id: Optional[str]) -> Optional[str]:
    """Resolve the virtual key a call should bill against.

    Phase 3 of the migration plan issues one key per user via the proxy's
    ``/key/generate`` and stores its id on the user row. Until that lands every
    call uses the platform key, so budgets are enforced globally rather than
    per-user -- a strict improvement over no enforcement, and the interface here
    does not change when per-user keys arrive.
    """
    settings = _settings()
    return getattr(settings, "LITELLM_PROXY_API_KEY", None) or None
