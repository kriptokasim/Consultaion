"""Canonical model registry and alias resolution for the Model Gateway.

Every real model has one canonical key with full metadata. Backward-compatible
names are stored in MODEL_ALIASES and resolved transparently.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("model_gateway.model_map")

MODEL_MAP: dict[str, dict[str, Any]] = {
    "openai_fast": {"provider":"openai","provider_model_id":"gpt-4o-mini","litellm_model":"openai/gpt-4o-mini","cost_class":"cheap","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "openai_premium": {"provider":"openai","provider_model_id":"gpt-4o","litellm_model":"openai/gpt-4o","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "anthropic_reasoning": {"provider":"anthropic","provider_model_id":"claude-3-5-sonnet-20240620","litellm_model":"anthropic/claude-3-5-sonnet-20240620","cost_class":"paid","deprecated":True,"replacement":"anthropic_reasoning_current","last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":"Legacy alias retained for durable configs; runtime health decides availability."},
    "gemini_general": {"provider":"gemini","provider_model_id":"gemini-3.7-flash","litellm_model":"gemini/gemini-3.7-flash","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":"Google Gemini API","free_tier_limit_notes":"Current production model; availability/pricing is account dependent."},
    "gemini_pro": {"provider":"gemini","provider_model_id":"gemini-3.7-flash","litellm_model":"gemini/gemini-3.7-flash","cost_class":"paid","deprecated":True,"replacement":"gemini_general","last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":"Google Gemini API","free_tier_limit_notes":"Legacy pro preset migrated to current Flash model."},
    "groq_fast": {"provider":"groq","provider_model_id":"openai/gpt-oss-20b","litellm_model":"groq/openai/gpt-oss-20b","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"Groq GPT-OSS 20B availability","free_tier_limit_notes":"Use account/developer-plan limits; model is current production-supported."},
    "deepinfra_reasoning": {"provider":"deepinfra","provider_model_id":"meta-llama/Llama-3.3-70B-Instruct","litellm_model":"deepinfra/meta-llama/Llama-3.3-70B-Instruct","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"DeepInfra free tier for open models","free_tier_limit_notes":"Limited free credits on signup."},
    "together_general": {"provider":"together","provider_model_id":"meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo","litellm_model":"together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"Together AI free tier","free_tier_limit_notes":"Free credits on signup; rate-limited."},
    "fireworks_general": {"provider":"fireworks","provider_model_id":"accounts/fireworks/models/llama-v3p1-8b-instruct","litellm_model":"fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"Fireworks free tier","free_tier_limit_notes":"Free credits on signup; rate-limited."},
    "perplexity_search": {"provider":"perplexity","provider_model_id":"sonar-reasoning","litellm_model":"perplexity/sonar-reasoning","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "xai_grok": {"provider":"xai","provider_model_id":"grok-2","litellm_model":"xai/grok-2","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "mistral_large": {"provider":"mistral","provider_model_id":"mistral-large-latest","litellm_model":"mistral/mistral-large-latest","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "openrouter_fallback": {"provider":"openrouter","provider_model_id":"openrouter/free","litellm_model":"openrouter/openrouter/free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter Free Router","free_tier_limit_notes":"Selects from currently available free endpoints; rate limited."},
    "router-smart": {"provider":"openrouter","provider_model_id":"openrouter/free","litellm_model":"openrouter/openrouter/free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter Free Router","free_tier_limit_notes":"Free router; upstream model selection is dynamic."},
    "router-deep": {"provider":"openrouter","provider_model_id":"z-ai/glm-5.2:free","litellm_model":"openrouter/z-ai/glm-5.2:free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Free endpoint; rate limited."},
    "llama-3-free": {"provider":"openrouter","provider_model_id":"openai/gpt-oss-20b:free","litellm_model":"openrouter/openai/gpt-oss-20b:free","cost_class":"free","deprecated":True,"replacement":"openrouter_fallback","last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Legacy key retained for persisted panels."},
    "mimo-v2-free": {"provider":"openrouter","provider_model_id":"openai/gpt-oss-20b:free","litellm_model":"openrouter/openai/gpt-oss-20b:free","cost_class":"free","deprecated":True,"replacement":"openrouter_fallback","last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Legacy key retained for persisted panels."},
    "deepseek-r1": {"provider":"openrouter","provider_model_id":"deepseek/deepseek-r1","litellm_model":"openrouter/deepseek/deepseek-r1","cost_class":"medium","deprecated":False,"replacement":None,"last_verified_at":"2026-06-28","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
}

MODEL_ALIASES: dict[str, str] = {
    "gpt4o-mini":"openai_fast","gpt4o-deep":"openai_premium","claude-sonnet":"anthropic_reasoning","claude-haiku":"anthropic_reasoning",
    "gemini-2-flash":"gemini_general","gemini-2-5-pro":"gemini_pro","groq-llama-3-3":"groq_fast","mistral-large":"mistral_large",
    "gpt-4o-mini":"openai_fast","gpt-4.1-mini":"openai_fast","gpt-4o":"openai_premium","claude-3-5-sonnet":"anthropic_reasoning","claude-3-5-haiku":"anthropic_reasoning",
    "gemini-1.5-flash":"gemini_general","gemini-1.5-pro":"gemini_pro",
    "openai/gpt-4o-mini":"openai_fast","openai/gpt-4o":"openai_premium","anthropic/claude-3-5-sonnet-20240620":"anthropic_reasoning","anthropic/claude-3-haiku-20240307":"anthropic_reasoning",
    "gemini/gemini-2.0-flash":"gemini_general","gemini/gemini-2.5-pro-preview-06-05":"gemini_pro","groq/llama-3.3-70b-versatile":"groq_fast","mistral/mistral-large-latest":"mistral_large",
    "openrouter/deepseek/deepseek-r1":"deepseek-r1",
}

class ModelKeyError(Exception):
    """Raised when a model key cannot be resolved."""
    pass

def resolve_model_key(model_key: str) -> str:
    if model_key in MODEL_MAP:
        return model_key
    canonical = MODEL_ALIASES.get(model_key)
    if canonical is not None:
        logger.warning("Deprecated model alias '%s' used — resolved to '%s'.", model_key, canonical)
        return canonical
    raise ModelKeyError(f"Unknown model key '{model_key}'. Valid canonical keys: {sorted(MODEL_MAP.keys())}.")

def get_model_cost_class(model_key: str) -> str:
    return MODEL_MAP.get(model_key, {}).get("cost_class", "unknown")

def is_free_model(model_key: str) -> bool:
    return get_model_cost_class(model_key) == "free"
