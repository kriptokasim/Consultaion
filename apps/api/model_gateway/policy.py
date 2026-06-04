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
            "pytest" in sys.modules or
            (len(sys.argv) > 0 and "pytest" in sys.argv[0])
        )
    )
    if is_testing:
        return MockAdapter, "mock-policy"
    
    policy = request.gateway_policy
    
    if policy == "direct":
        return DirectProviderAdapter, "direct-only"
    
    if policy == "fallback":
        # Primary is direct provider, fallback handles OpenRouter
        return DirectProviderAdapter, "fallback-chain"
        
    # Auto: default strategy
    # Smart routing based on user plan and requested model
    if request.user_plan == "free":
        return OpenRouterAdapter, "smart-router-free"
    
    return DirectProviderAdapter, "direct-smart-pro"
