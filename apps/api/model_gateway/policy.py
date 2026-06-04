from typing import Tuple, Type
import os
import sys
from model_gateway.types import GatewayRequest
from model_gateway.adapters import BaseAdapter, DirectProviderAdapter, OpenRouterAdapter, MockAdapter

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
        return DirectProviderAdapter, "pro-direct-pool"
    
    if policy == "fallback":
        return DirectProviderAdapter, "openrouter-fallback-pool"
        
    # Auto smart routing:
    # If the user has an enterprise tier, direct/private routes only (no public aggregators).
    if request.user_plan == "enterprise":
        return DirectProviderAdapter, "enterprise-private-pool"
        
    # If free plan, route through the free hosted low-cost pool
    if request.user_plan == "free":
        return OpenRouterAdapter, "smart-router-free"
    
    # Default to pro-direct-pool/direct-smart-pro for pro/other users
    return DirectProviderAdapter, "direct-smart-pro"


