import os
import sys
from typing import Tuple, Type

from model_gateway.adapters import (
    BaseAdapter,
    DirectProviderAdapter,
    MockAdapter,
)
from model_gateway.types import GatewayRequest


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


