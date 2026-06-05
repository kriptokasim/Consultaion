import os
from typing import Dict, List, Optional
from model_gateway.types import GatewayModelRestrictedError

DEFAULT_POOLS = {
    "pools": {
        "test_pool": {
            "models": ["mock", "groq_fast", "deepinfra_reasoning"],
            "policies": ["auto", "direct"]
        },
        "free_hosted_pool": {
            "models": ["groq_fast", "deepinfra_reasoning", "together_general", "fireworks_general"],
            "policies": ["auto", "direct"]
        },
        "arena_primary_pool": {
            "models": ["openai_fast", "anthropic_reasoning", "gemini_general", "groq_fast"],
            "policies": ["auto", "direct", "fallback"]
        },
        "premium_pool": {
            "models": [
                "openai_premium",
                "anthropic_reasoning",
                "gemini_pro",
                "perplexity_search",
                "xai_grok",
                "mistral_large"
            ],
            "policies": ["auto", "direct", "fallback"]
        },
        "fallback_pool": {
            "models": ["openrouter_fallback"],
            "policies": ["auto", "fallback"]
        },
        "demo_pool": {
            "models": ["mock"],
            "policies": ["auto", "direct"]
        }
    }
}

def load_pools_config() -> Dict:
    try:
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "model_pools.yaml"
        )
        if os.path.exists(yaml_path):
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    return data
    except Exception:
        pass
    return DEFAULT_POOLS

def get_model_pool(model_id: str) -> str:
    """Find which pool a model belongs to. Default to premium_pool if unknown/advanced."""
    if model_id == "custom-model" or model_id.startswith("custom-"):
        return "free_hosted_pool"
    
    # Map legacy IDs to new pool structures
    legacy_pools = {
        "mimo-v2-free": "free_hosted_pool",
        "llama-3-free": "free_hosted_pool",
        "gpt4o-mini": "arena_primary_pool",
        "gpt4o-deep": "premium_pool",
        "claude-sonnet": "premium_pool",
        "claude-haiku": "arena_primary_pool",
        "gemini-2-flash": "arena_primary_pool",
        "gemini-2-5-pro": "premium_pool",
        "groq-llama-3-3": "arena_primary_pool",
        "mistral-large": "premium_pool",
        "deepseek-r1": "premium_pool",
        "router-smart": "fallback_pool",
        "router-deep": "fallback_pool",
    }
    if model_id in legacy_pools:
        return legacy_pools[model_id]
        
    config = load_pools_config()
    pools = config.get("pools", {})
    for pool_name, pool_info in pools.items():
        if model_id in pool_info.get("models", []):
            return pool_name
    return "premium_pool"


def validate_user_access_to_model(model_id: str, user_plan: Optional[str], has_credits: bool = False) -> None:
    """Standard plan or Free plan checks."""
    if has_credits:
        return
    plan = (user_plan or "free").lower()
    pool = get_model_pool(model_id)
    if plan == "free":
        # Under the new system, premium_pool is restricted to Pro plan users
        if pool in ("premium_pool", "pro_pool"):
            raise GatewayModelRestrictedError(
                f"Model {model_id} is restricted to Pro plan users. Please upgrade."
            )
