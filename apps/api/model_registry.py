import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ModelProvider(str, Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    POE = "poe"


@dataclass
class ModelConfig:
    id: str
    display_name: str
    provider: ModelProvider
    litellm_model: str
    tags: List[str]
    max_context: Optional[int] = None
    recommended: bool = False
    enabled: bool = True


ALL_MODELS: Dict[str, ModelConfig] = {
    "router-smart": ModelConfig(
        id="router-smart",
        display_name="Smart Router (OpenRouter)",
        provider=ModelProvider.OPENROUTER,
        litellm_model="openrouter/router",
        tags=["default", "balanced", "routing"],
        recommended=True,
    ),
    "router-deep": ModelConfig(
        id="router-deep",
        display_name="Deep Router (OpenRouter)",
        provider=ModelProvider.OPENROUTER,
        litellm_model="openrouter/auto",
        tags=["reasoning", "deep"],
    ),
    "gpt4o-mini": ModelConfig(
        id="gpt4o-mini",
        display_name="GPT-4.1 Mini (OpenAI)",
        provider=ModelProvider.OPENAI,
        litellm_model="openai/gpt-4.1-mini",
        tags=["fast", "cheap"],
    ),
    "gpt4o-deep": ModelConfig(
        id="gpt4o-deep",
        display_name="GPT-4.1 Deep (OpenAI)",
        provider=ModelProvider.OPENAI,
        litellm_model="openai/gpt-4.1",
        tags=["reasoning"],
    ),
    "claude-sonnet": ModelConfig(
        id="claude-sonnet",
        display_name="Claude 3.5 Sonnet (Anthropic)",
        provider=ModelProvider.ANTHROPIC,
        litellm_model="anthropic/claude-3.5-sonnet",
        tags=["reasoning", "balanced"],
    ),
    "claude-haiku": ModelConfig(
        id="claude-haiku",
        display_name="Claude 3.5 Haiku (Anthropic)",
        provider=ModelProvider.ANTHROPIC,
        litellm_model="anthropic/claude-3.5-haiku",
        tags=["fast", "cheap"],
    ),
    "gemini-flash": ModelConfig(
        id="gemini-flash",
        display_name="Gemini 2.0 Flash",
        provider=ModelProvider.GEMINI,
        litellm_model="gemini/gemini-2.0-flash",
        tags=["fast", "balanced"],
    ),
    "gemini-pro": ModelConfig(
        id="gemini-pro",
        display_name="Gemini 2.0 Pro",
        provider=ModelProvider.GEMINI,
        litellm_model="gemini/gemini-2.0-pro",
        tags=["reasoning"],
    ),
    "deepseek-reasoner": ModelConfig(
        id="deepseek-reasoner",
        display_name="DeepSeek Reasoner (Experimental via OpenRouter)",
        provider=ModelProvider.OPENROUTER,
        litellm_model="openrouter/deepseek/deepseek-reasoner",
        tags=["experimental", "reasoning"],
        enabled=False,
    ),
}


def _provider_enabled(provider: ModelProvider) -> bool:
    if os.getenv("USE_MOCK", "0") == "1":
        return True
    if provider == ModelProvider.OPENROUTER:
        return bool(os.getenv("OPENROUTER_API_KEY"))
    if provider == ModelProvider.OPENAI:
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == ModelProvider.ANTHROPIC:
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == ModelProvider.GEMINI:
        return bool(os.getenv("GEMINI_API_KEY"))
    return False


def list_enabled_models() -> List[ModelConfig]:
    enabled: List[ModelConfig] = []
    for cfg in ALL_MODELS.values():
        if not cfg.enabled:
            continue
        if not _provider_enabled(cfg.provider):
            continue
        enabled.append(cfg)
    return enabled


def get_model(model_id: str) -> ModelConfig:
    if model_id not in ALL_MODELS:
        raise ValueError(f"Unknown model: {model_id}")
    return ALL_MODELS[model_id]


def get_default_model() -> ModelConfig:
    enabled = list_enabled_models()
    for model in enabled:
        if model.recommended:
            return model
    if enabled:
        return enabled[0]
    raise RuntimeError("No models are enabled; configure at least one provider API key.")
