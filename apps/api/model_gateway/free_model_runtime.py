"""Runtime compatibility layer for fast-moving free-model catalogs.

Provider model slugs change faster than persisted Debate.panel_config IDs. Keep
Consultaion's stable canonical IDs while updating the concrete upstream targets
at process boot. This preserves old database/frontend identities without forcing
an immediate data migration.

The choices below were verified against provider documentation on 2026-08-30:
- Gemini free tier: gemini-3.7-flash
- Groq free-plan model: openai/gpt-oss-20b
- OpenRouter free router: openrouter/free
- Explicit OpenRouter free seats: GPT-OSS 20B, GLM 5.2, Nemotron 3 Super
"""

from __future__ import annotations

_installed = False


def install_current_free_model_targets() -> None:
    global _installed
    if _installed:
        return

    from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP

    # Stable canonical IDs, refreshed upstream targets.
    MODEL_MAP["gemini_general"].update(
        {
            "provider_model_id": "gemini-3.7-flash",
            "litellm_model": "gemini/gemini-3.7-flash",
            "cost_class": "free",
            "last_verified_at": "2026-08-30",
            "free_tier_verified_at": "2026-08-30",
            "free_tier_source": "Google Gemini Developer API free tier",
            "free_tier_limit_notes": "Free-tier availability and rate limits apply.",
        }
    )
    MODEL_MAP["groq_fast"].update(
        {
            "provider_model_id": "openai/gpt-oss-20b",
            "litellm_model": "groq/openai/gpt-oss-20b",
            "cost_class": "free",
            "last_verified_at": "2026-08-30",
            "free_tier_verified_at": "2026-08-30",
            "free_tier_source": "Groq free plan",
            "free_tier_limit_notes": "Free plan currently lists 30 RPM / 1000 RPD / 8K TPM / 200K TPD.",
        }
    )
    MODEL_MAP["openrouter_fallback"].update(
        {
            "provider_model_id": "openrouter/free",
            "litellm_model": "openrouter/openrouter/free",
            "cost_class": "free",
            "last_verified_at": "2026-08-30",
            "free_tier_verified_at": "2026-08-30",
            "free_tier_source": "OpenRouter Free Models Router",
            "free_tier_limit_notes": "Zero token price; OpenRouter free-account rate limits apply.",
        }
    )

    # Explicit free OpenRouter seats provide diversity and deterministic model
    # identity while the free router remains the churn-resistant final fallback.
    MODEL_MAP["openrouter_gpt_oss_free"] = {
        "provider": "openrouter",
        "provider_model_id": "openai/gpt-oss-20b:free",
        "litellm_model": "openrouter/openai/gpt-oss-20b:free",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-08-30",
        "free_tier_verified_at": "2026-08-30",
        "free_tier_source": "OpenRouter",
        "free_tier_limit_notes": "Free endpoint; rate limited.",
    }
    MODEL_MAP["openrouter_glm_free"] = {
        "provider": "openrouter",
        "provider_model_id": "z-ai/glm-5.2:free",
        "litellm_model": "openrouter/z-ai/glm-5.2:free",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-08-30",
        "free_tier_verified_at": "2026-08-30",
        "free_tier_source": "OpenRouter",
        "free_tier_limit_notes": "Free endpoint; rate limited.",
    }
    MODEL_MAP["openrouter_nemotron_free"] = {
        "provider": "openrouter",
        "provider_model_id": "nvidia/nemotron-3-super-120b-a12b:free",
        "litellm_model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "cost_class": "free",
        "deprecated": False,
        "replacement": None,
        "last_verified_at": "2026-08-30",
        "free_tier_verified_at": "2026-08-30",
        "free_tier_source": "OpenRouter",
        "free_tier_limit_notes": "Free endpoint; rate limited.",
    }

    # Preserve old persisted aliases but point new direct LiteLLM strings back to
    # the same stable canonical identities.
    MODEL_ALIASES.update(
        {
            "gemini/gemini-3.7-flash": "gemini_general",
            "groq/openai/gpt-oss-20b": "groq_fast",
            "openrouter/openrouter/free": "openrouter_fallback",
            "openrouter/openai/gpt-oss-20b:free": "openrouter_gpt_oss_free",
            "openrouter/z-ai/glm-5.2:free": "openrouter_glm_free",
            "openrouter/nvidia/nemotron-3-super-120b-a12b:free": "openrouter_nemotron_free",
        }
    )

    # OpenRouterAdapter keeps a static compatibility table for historical IDs.
    from model_gateway.adapters import OpenRouterAdapter

    OpenRouterAdapter._STATIC_MAPPING.update(
        {
            "gemini-2-flash": "openrouter/openrouter/free",
            "groq-llama-3-3": "openrouter/openai/gpt-oss-20b:free",
            "gemini_general": "openrouter/openrouter/free",
            "groq_fast": "openrouter/openai/gpt-oss-20b:free",
            "openrouter_fallback": "openrouter/openrouter/free",
        }
    )

    _installed = True
