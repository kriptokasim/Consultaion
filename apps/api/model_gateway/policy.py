import os
import sys
from typing import Tuple, Type

from model_gateway.adapters import (
    BaseAdapter,
    DirectProviderAdapter,
    MockAdapter,
)
from model_gateway.types import GatewayRequest


def _model_uses_openrouter(model_id: str) -> bool:
    """Return True if *model_id* should be routed through OpenRouter.

    Checks four paths (in order):
    1. Explicit ``openrouter/`` prefix in the model_id string.
    2. Canonical key exists in MODEL_MAP with ``provider == "openrouter"``.
    3. Alias resolves to a canonical key whose provider is ``"openrouter"``.
    4. Parliament model registry entry with ``provider == "openrouter"``.
    """
    if model_id.startswith("openrouter/"):
        return True

    # Check MODEL_MAP (fast path)
    from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP

    record = MODEL_MAP.get(model_id)
    if record:
        return record.get("provider") == "openrouter"

    canonical = MODEL_ALIASES.get(model_id)
    if canonical:
        record = MODEL_MAP.get(canonical)
        if record:
            return record.get("provider") == "openrouter"

    # Check parliament registry (catches free-tier models not in MODEL_MAP)
    try:
        from parliament.model_registry import get_model_info
        info = get_model_info(model_id)
        if info:
            return info.provider == "openrouter"
    except Exception:
        pass

    return False


def determine_routing_strategy(
    request: GatewayRequest,
    force_real: bool = False
) -> Tuple[Type[BaseAdapter], str]:
    """Decide which adapter to use and the routing policy label."""
    # Check if we are running in local/test/mock mode
    is_testing = (
        not force_real and (
            os.getenv("MOCK_LLM") == "true" or
            os.getenv("TESTING") == "true" or
            ("pytest" in sys.modules and os.getenv("USE_MOCK") != "0") or
            (len(sys.argv) > 0 and "pytest" in sys.argv[0] and os.getenv("USE_MOCK") != "0")
        )
    )
    if is_testing:

        return MockAdapter, "demo-pool"
    
    policy = request.gateway_policy
    
    if policy == "direct":
        return DirectProviderAdapter, "direct-smart-pro"
    
    if policy == "fallback":
        return DirectProviderAdapter, "direct-fallback-pro"
        
    # Auto smart routing:
    # If the user has an enterprise tier, direct/private routes only (no public aggregators).
    if request.user_plan == "enterprise":
        return DirectProviderAdapter, "enterprise-private-pool"
        
    # If free plan, route through the free hosted pool directly
    if request.user_plan == "free":
        return DirectProviderAdapter, "free-direct-pool"
    
    # Default to direct-smart-pro for pro/other users
    return DirectProviderAdapter, "direct-smart-pro"


