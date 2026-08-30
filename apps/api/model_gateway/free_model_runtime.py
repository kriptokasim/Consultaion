"""Runtime compatibility layer for fast-moving provider model catalogs."""
from __future__ import annotations

_installed = False


def install_current_free_model_targets() -> None:
    global _installed
    if _installed:
        return

    from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP

    # Gemini 3.7 Flash is the current production model, but its current public
    # API pricing is not zero. Do not label it as free-only; paid credentials or
    # an upstream OpenRouter free route must be used when the user has no Gemini
    # budget. The stable model ID is still refreshed here for legacy configs.
    MODEL_MAP["gemini_general"].update(
        {
            "provider_model_id": "gemini-3.7-flash",
            "litellm_model": "gemini/gemini-3.7-flash",
            "cost_class": "paid",
            "last_verified_at": "2026-08-30",
            "free_tier_verified_at": None,
            "free_tier_source": "Google Gemini API",
            "free_tier_limit_notes": "Current production model; account pricing and limits apply.",
        }
    )
    MODEL_MAP["groq_fast"].update(
        {
            "provider_model_id": "openai/gpt-oss-20b",
            "litellm_model": "groq/openai/gpt-oss-20b",
            "cost_class": "free",
            "last_verified_at": "2026-08-30",
            "free_tier_verified_at": "2026-08-30",
            "free_tier_source": "Groq GPT-OSS 20B",
            "free_tier_limit_notes": "Use current account/developer-plan limits.",
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
            "free_tier_limit_notes": "Zero token price; free-account rate limits apply.",
        }
    )

    MODEL_MAP["openrouter_gpt_oss_free"] = {
        "provider":"openrouter","provider_model_id":"openai/gpt-oss-20b:free","litellm_model":"openrouter/openai/gpt-oss-20b:free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Free endpoint; rate limited.",
    }
    MODEL_MAP["openrouter_glm_free"] = {
        "provider":"openrouter","provider_model_id":"z-ai/glm-5.2:free","litellm_model":"openrouter/z-ai/glm-5.2:free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Free endpoint; rate limited.",
    }
    MODEL_MAP["openrouter_nemotron_free"] = {
        "provider":"openrouter","provider_model_id":"nvidia/nemotron-3-super-120b-a12b:free","litellm_model":"openrouter/nvidia/nemotron-3-super-120b-a12b:free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Free endpoint; rate limited.",
    }

    MODEL_ALIASES.update({
        "gemini/gemini-3.7-flash":"gemini_general",
        "groq/openai/gpt-oss-20b":"groq_fast",
        "openrouter/openrouter/free":"openrouter_fallback",
        "openrouter/openai/gpt-oss-20b:free":"openrouter_gpt_oss_free",
        "openrouter/z-ai/glm-5.2:free":"openrouter_glm_free",
        "openrouter/nvidia/nemotron-3-super-120b-a12b:free":"openrouter_nemotron_free",
    })

    from model_gateway.adapters import OpenRouterAdapter
    OpenRouterAdapter._STATIC_MAPPING.update({
        "gemini-2-flash":"openrouter/openrouter/free",
        "groq-llama-3-3":"openrouter/openai/gpt-oss-20b:free",
        "gemini_general":"openrouter/openrouter/free",
        "groq_fast":"openrouter/openai/gpt-oss-20b:free",
        "openrouter_fallback":"openrouter/openrouter/free",
        "router-smart":"openrouter/openrouter/free",
        "router-deep":"openrouter/z-ai/glm-5.2:free",
        "llama-3-free":"openrouter/openai/gpt-oss-20b:free",
    })
    _installed = True
