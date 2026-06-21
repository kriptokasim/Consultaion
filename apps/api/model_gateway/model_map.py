"""Canonical model registry and alias resolution for the Model Gateway.

Every real model has one canonical key with full metadata. Backward-compatible
names are stored in MODEL_ALIASES and resolved transparently.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("model_gateway.model_map")

# ── Canonical model records ─────────────────────────────────────────────
# Each entry is the single source of truth for a model. Duplicate aliases
# must NOT appear here — use MODEL_ALIASES below.

MODEL_MAP: dict[str, dict[str, Any]] = {
    # ── OpenAI ──────────────────────────────────────────────────────────
    "openai_fast": {
        "provider": "openai",
        "provider_model_id": "gpt-4o-mini",
        "litellm_model": "openai/gpt-4o-mini",
        "cost_class": "cheap",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },
    "openai_premium": {
        "provider": "openai",
        "provider_model_id": "gpt-4o",
        "litellm_model": "openai/gpt-4o",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── Anthropic ───────────────────────────────────────────────────────
    "anthropic_reasoning": {
        "provider": "anthropic",
        "provider_model_id": "claude-3-5-sonnet-20240620",
        "litellm_model": "anthropic/claude-3-5-sonnet-20240620",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── Google Gemini ───────────────────────────────────────────────────
    "gemini_general": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.0-flash",
        "litellm_model": "gemini/gemini-2.0-flash",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": "2026-06-21",
        "free_tier_source": "Google AI Studio free tier",
        "free_tier_limit_notes": "Rate-limited; 15 RPM / 1M TPD on free tier",
    },
    "gemini_pro": {
        "provider": "gemini",
        "provider_model_id": "gemini-2.5-pro-preview-06-05",
        "litellm_model": "gemini/gemini-2.5-pro-preview-06-05",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── Groq ────────────────────────────────────────────────────────────
    "groq_fast": {
        "provider": "groq",
        "provider_model_id": "llama-3.3-70b-versatile",
        "litellm_model": "groq/llama-3.3-70b-versatile",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": "2026-06-21",
        "free_tier_source": "Groq free API tier",
        "free_tier_limit_notes": "Rate-limited; 30 RPM / 14400 RPD on free tier",
    },

    # ── DeepInfra ───────────────────────────────────────────────────────
    "deepinfra_reasoning": {
        "provider": "deepinfra",
        "provider_model_id": "meta-llama/Llama-3.3-70B-Instruct",
        "litellm_model": "deepinfra/meta-llama/Llama-3.3-70B-Instruct",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": "2026-06-21",
        "free_tier_source": "DeepInfra free tier for open models",
        "free_tier_limit_notes": "Limited free credits on signup",
    },

    # ── Together AI ─────────────────────────────────────────────────────
    "together_general": {
        "provider": "together",
        "provider_model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "litellm_model": "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": "2026-06-21",
        "free_tier_source": "Together AI free tier",
        "free_tier_limit_notes": "Free credits on signup; rate-limited",
    },

    # ── Fireworks ───────────────────────────────────────────────────────
    "fireworks_general": {
        "provider": "fireworks",
        "provider_model_id": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "litellm_model": "fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": "2026-06-21",
        "free_tier_source": "Fireworks free tier",
        "free_tier_limit_notes": "Free credits on signup; rate-limited",
    },

    # ── Perplexity ──────────────────────────────────────────────────────
    "perplexity_search": {
        "provider": "perplexity",
        "provider_model_id": "sonar-reasoning",
        "litellm_model": "perplexity/sonar-reasoning",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── xAI ─────────────────────────────────────────────────────────────
    "xai_grok": {
        "provider": "xai",
        "provider_model_id": "grok-2",
        "litellm_model": "xai/grok-2",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── Mistral ─────────────────────────────────────────────────────────
    "mistral_large": {
        "provider": "mistral",
        "provider_model_id": "mistral-large-latest",
        "litellm_model": "mistral/mistral-large-latest",
        "cost_class": "paid",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": None,
    },

    # ── OpenRouter (fallback) ───────────────────────────────────────────
    "openrouter_fallback": {
        "provider": "openrouter",
        "provider_model_id": "openai/gpt-4o-mini",
        "litellm_model": "openrouter/openai/gpt-4o-mini",
        "cost_class": "unknown",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-06-21",
        "free_tier_verified_at": None,
        "free_tier_source": None,
        "free_tier_limit_notes": "Cost depends on upstream model routing",
    },
}

# ── Backward-compatible aliases ─────────────────────────────────────────
# These keys should NOT appear in MODEL_MAP. They resolve to canonical keys.
# Using an alias logs a deprecation warning.

MODEL_ALIASES: dict[str, str] = {
    "gpt4o-mini": "openai_fast",
    "gpt4o-deep": "openai_premium",
    "claude-sonnet": "anthropic_reasoning",
    "claude-haiku": "anthropic_reasoning",
    "gemini-2-flash": "gemini_general",
    "gemini-2-5-pro": "gemini_pro",
    "groq-llama-3-3": "groq_fast",
    "mistral-large": "mistral_large",
    "deepseek-r1": "openrouter_fallback",
    "router-smart": "openrouter_fallback",
    "router-deep": "openrouter_fallback",
}


class ModelKeyError(Exception):
    """Raised when a model key cannot be resolved."""
    pass


def resolve_model_key(model_key: str) -> str:
    """Resolve a model key to its canonical form.

    - If *model_key* is a canonical key, return it unchanged.
    - If *model_key* is a deprecated alias, return the canonical key and
      log a deprecation warning.
    - If *model_key* is unknown, raise :class:`ModelKeyError`.
    """
    if model_key in MODEL_MAP:
        return model_key

    canonical = MODEL_ALIASES.get(model_key)
    if canonical is not None:
        logger.warning(
            "Deprecated model alias '%s' used — resolved to canonical key '%s'. "
            "Update your configuration to use the canonical key directly.",
            model_key,
            canonical,
        )
        return canonical

    raise ModelKeyError(
        f"Unknown model key '{model_key}'. "
        f"Valid canonical keys: {sorted(MODEL_MAP.keys())}. "
        f"Valid aliases: {sorted(MODEL_ALIASES.keys())}."
    )


def get_model_cost_class(model_key: str) -> str:
    """Return the cost_class for a resolved canonical model key.

    Returns 'unknown' if the key is not found (should not happen after
    resolve_model_key).
    """
    record = MODEL_MAP.get(model_key, {})
    return record.get("cost_class", "unknown")


def is_free_model(model_key: str) -> bool:
    """Return True only if the model's cost_class is explicitly 'free'."""
    return get_model_cost_class(model_key) == "free"
