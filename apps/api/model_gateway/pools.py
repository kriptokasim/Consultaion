import os
from typing import Dict, List, Optional
from model_gateway.types import GatewayModelRestrictedError

DEFAULT_POOLS = {
    "pools": {
        "free_pool": {
            "models": ["mimo-v2-free", "llama-3-free"],
            "policies": ["auto", "direct"]
        },
        "pro_pool": {
            "models": [
                "gpt4o-mini",
                "gpt4o-deep",
                "claude-sonnet",
                "claude-haiku",
                "gemini-2-flash",
                "gemini-2-5-pro",
                "groq-llama-3-3",
                "mistral-large",
                "deepseek-r1"
            ],
            "policies": ["auto", "direct", "fallback"]
        },
        "fallback_pool": {
            "models": ["router-smart", "router-deep"],
            "policies": ["auto", "fallback"]
        }
    },
    "providers": {
        "openai": {
            "direct_model": "openai/gpt-4o",
            "fallback_model": "openrouter/openai/gpt-4o"
        },
        "anthropic": {
            "direct_model": "anthropic/claude-3-5-sonnet-20240620",
            "fallback_model": "openrouter/anthropic/claude-3.5-sonnet"
        },
        "gemini": {
            "direct_model": "gemini/gemini-2.5-pro-preview-06-05",
            "fallback_model": "openrouter/google/gemini-2.5-pro"
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
    """Find which pool a model belongs to. Default to pro_pool if unknown."""
    if model_id == "custom-model" or model_id.startswith("custom-"):
        return "free_pool"
    config = load_pools_config()
    pools = config.get("pools", {})
    for pool_name, pool_info in pools.items():
        if model_id in pool_info.get("models", []):
            return pool_name
    return "pro_pool"


def validate_user_access_to_model(model_id: str, user_plan: Optional[str], has_credits: bool = False) -> None:
    """Standard plan or Free plan checks."""
    if has_credits:
        return
    plan = (user_plan or "free").lower()
    pool = get_model_pool(model_id)
    if plan == "free" and pool == "pro_pool":
        raise GatewayModelRestrictedError(
            f"Model {model_id} is restricted to Pro plan users. Please upgrade."
        )
