from typing import List, Literal, Optional, Set

from config import settings
from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str = Field(..., description="The unique identifier for the model (e.g. 'gpt4o-mini')")
    display_name: str = Field(..., description="Human-readable name")
    provider: str = Field(..., description="The provider identifier (e.g. 'openai', 'anthropic')")
    litellm_model: str = Field(..., description="The model string passed to litellm")
    
    # Capabilities
    capabilities: Set[str] = Field(default_factory=set, description="Set of capabilities like 'chat', 'tools', 'vision'")
    
    # Tiers & Classifications
    tier: Literal["standard", "advanced"] = Field(default="standard", description="The billing tier for this model")
    cost_tier: Literal["low", "medium", "high"]
    latency_class: Literal["fast", "normal", "slow"]
    quality_tier: Literal["baseline", "advanced", "flagship"]
    safety_profile: Literal["strict", "normal", "experimental"]
    
    # Status
    enabled: bool = True
    recommended: bool = False
    
    # Legacy/Optional
    tags: Optional[List[str]] = None
    
    # Visual Identity
    logo_url: Optional[str] = Field(None, description="Path to the model logo (e.g. '/logos/openai.svg')")


# Define the registry
ALL_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="router-smart",
        display_name="Smart Router (OpenRouter)",
        provider="openrouter",
        litellm_model="openrouter/router",
        capabilities={"chat", "routing"},
        tier="standard",
        cost_tier="medium",
        latency_class="normal",
        quality_tier="advanced",
        safety_profile="normal",
        recommended=True,
        logo_url="/logos/openrouter.svg",
    ),
    ModelInfo(
        id="router-deep",
        display_name="Deep Router (OpenRouter)",
        provider="openrouter",
        litellm_model="openrouter/auto",
        capabilities={"chat", "routing", "reasoning"},
        tier="advanced",
        cost_tier="high",
        latency_class="slow",
        quality_tier="flagship",
        safety_profile="normal",
        logo_url="/logos/openrouter.svg",
    ),
    ModelInfo(
        id="gpt4o-mini",
        display_name="GPT-4o Mini (OpenAI)",
        provider="openai",
        litellm_model="openai/gpt-4o-mini",
        capabilities={"chat", "tools", "vision"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="baseline",
        safety_profile="strict",
        logo_url="/logos/openai.svg",
    ),
    ModelInfo(
        id="gpt4o-deep",
        display_name="GPT-4o (OpenAI)",
        provider="openai",
        litellm_model="openai/gpt-4o",
        capabilities={"chat", "tools", "vision", "reasoning"},
        tier="advanced",
        cost_tier="high",
        latency_class="normal",
        quality_tier="flagship",
        safety_profile="strict",
        logo_url="/logos/openai.svg",
    ),
    ModelInfo(
        id="claude-sonnet",
        display_name="Claude 3.5 Sonnet (Anthropic)",
        provider="anthropic",
        litellm_model="anthropic/claude-3-5-sonnet-20240620",
        capabilities={"chat", "tools", "vision", "reasoning"},
        tier="advanced",
        cost_tier="medium",
        latency_class="normal",
        quality_tier="flagship",
        safety_profile="strict",
        logo_url="/logos/claude.svg",
    ),
    ModelInfo(
        id="claude-haiku",
        display_name="Claude 3 Haiku (Anthropic)",
        provider="anthropic",
        litellm_model="anthropic/claude-3-haiku-20240307",
        capabilities={"chat", "tools"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="baseline",
        safety_profile="strict",
        logo_url="/logos/claude.svg",
    ),
    ModelInfo(
        id="gemini-2-flash",
        display_name="Gemini 2.0 Flash",
        provider="gemini",
        litellm_model="gemini/gemini-2.0-flash",
        capabilities={"chat", "tools", "vision", "long_context"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="advanced",
        safety_profile="normal",
        logo_url="/logos/googlegemini.svg",
    ),
    ModelInfo(
        id="gemini-2-5-pro",
        display_name="Gemini 2.5 Pro",
        provider="gemini",
        litellm_model="gemini/gemini-2.5-pro-preview-06-05",
        capabilities={"chat", "tools", "vision", "long_context", "reasoning"},
        tier="advanced",
        cost_tier="medium",
        latency_class="normal",
        quality_tier="flagship",
        safety_profile="normal",
        logo_url="/logos/googlegemini.svg",
    ),
    ModelInfo(
        id="groq-llama-3-3",
        display_name="Llama 3.3 70B (Groq)",
        provider="groq",
        litellm_model="groq/llama-3.3-70b-versatile",
        capabilities={"chat", "tools"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="advanced",
        safety_profile="normal",
        logo_url="/logos/groq.svg",
    ),
    ModelInfo(
        id="llama-3-free",
        display_name="Llama 3 8B (Free)",
        provider="openrouter",
        litellm_model="openrouter/meta-llama/llama-3-8b-instruct:free",
        capabilities={"chat"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="baseline",
        safety_profile="normal",
        logo_url="/logos/openrouter.svg",
    ),
    ModelInfo(
        id="mimo-v2-free",
        display_name="MiMo v2 Flash (Free)",
        provider="openrouter",
        litellm_model="openrouter/xiaomi/mimo-vl-1b-v2:free",
        capabilities={"chat", "vision"},
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="baseline",
        safety_profile="experimental",
        logo_url="/logos/openrouter.svg",
    ),
    ModelInfo(
        id="mistral-large",
        display_name="Mistral Large",
        provider="mistral",
        litellm_model="mistral/mistral-large-latest",
        capabilities={"chat", "tools", "reasoning"},
        tier="advanced",
        cost_tier="medium",
        latency_class="normal",
        quality_tier="flagship",
        safety_profile="normal",
        logo_url="/logos/mistralai.svg",
    ),
]


def _provider_enabled(provider: str) -> bool:
    if settings.USE_MOCK:
        return True
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    if provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    if provider == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY)
    if provider == "gemini":
        return bool(settings.GEMINI_API_KEY)
    if provider == "groq":
        return bool(settings.GROQ_API_KEY)
    if provider == "mistral":
        return bool(settings.MISTRAL_API_KEY)
    return False


def list_enabled_models() -> List[ModelInfo]:
    """Return a list of models that are enabled in config and have their provider keys set."""
    enabled_models: List[ModelInfo] = []
    for model in ALL_MODELS:
        if not model.enabled:
            continue
        if not _provider_enabled(model.provider):
            continue
        enabled_models.append(model)
    return enabled_models


def get_model_info(name: str) -> Optional[ModelInfo]:
    """Get model info by ID. Returns None if not found."""
    for model in ALL_MODELS:
        if model.id == name:
            return model
    return None


def get_default_model() -> ModelInfo:
    """Get the default recommended model from enabled models."""
    enabled = list_enabled_models()
    for model in enabled:
        if model.recommended:
            return model
    if enabled:
        return enabled[0]
    
    # Fallback if no models enabled (shouldn't happen in valid config)
    raise RuntimeError("No models are enabled; configure at least one provider API key.")


def get_model(model_id: str) -> ModelInfo:
    """Get model info by ID, raising ValueError if not found.
    
    This is a helper for backward compatibility and strict lookups.
    """
    info = get_model_info(model_id)
    if not info:
        raise ValueError(f"Unknown model: {model_id}")
    return info
