"""Runtime compatibility layer for fast-moving provider model catalogs."""
from __future__ import annotations

_installed = False


FREE_OPENROUTER_CANDIDATES = (
    "openrouter/openai/gpt-oss-20b:free",
    "openrouter/z-ai/glm-5.2:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
)


def install_current_free_model_targets() -> None:
    global _installed
    if _installed:
        return

    from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP

    # Gemini 3.7 Flash is current but paid/account-dependent; never label it
    # free-only. Free-first hosted routing uses OpenRouter/Groq instead.
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
        "openrouter-nemotron-free":"openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    })

    # The Free Router is itself a moving target. If a request to it fails before
    # producing output (for example provider capability mismatch), try concrete
    # free models through the same OpenRouter key before declaring ALL MODELS
    # FAILED. This is deliberately bounded and does not splice partial streams.
    if not getattr(OpenRouterAdapter, "_consultaion_free_cascade_installed", False):
        original_call = OpenRouterAdapter.call_llm
        original_stream = OpenRouterAdapter.stream_llm

        def _is_free_router_request(model_id: str) -> bool:
            resolved = OpenRouterAdapter._resolve_model(model_id)
            return resolved in {
                "openrouter/openrouter/free",
                "openrouter/openrouter/free:free",
            }

        async def _call_with_free_cascade(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, user_id=None, response_format=None, tools=None, tool_choice=None, api_key=None):
            result = await original_call(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, user_id, response_format, tools, tool_choice, api_key)
            if result.success or not _is_free_router_request(model_id):
                return result
            last = result
            for candidate in FREE_OPENROUTER_CANDIDATES:
                if candidate == OpenRouterAdapter._resolve_model(model_id):
                    continue
                candidate_result = await original_call(self, messages, candidate, temperature, max_tokens, "direct", "free-cascade", routing_policy, user_id, response_format, tools, tool_choice, api_key)
                if candidate_result.success:
                    candidate_result.fallback_used = True
                    candidate_result.fallback_reason = f"OpenRouter Free Router failed ({result.error_code or 'provider_error'}); concrete free candidate succeeded: {candidate}"
                    return candidate_result
                last = candidate_result
            return last

        async def _stream_with_free_cascade(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, on_delta, user_id=None, api_key=None):
            emitted = False
            async def _track(delta):
                nonlocal emitted
                if getattr(delta, "text", ""):
                    emitted = True
                await on_delta(delta)
            result = await original_stream(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, _track, user_id, api_key)
            if result.success or emitted or not _is_free_router_request(model_id):
                return result
            last = result
            for candidate in FREE_OPENROUTER_CANDIDATES:
                candidate_result = await original_stream(self, messages, candidate, temperature, max_tokens, "direct", "free-cascade", routing_policy, on_delta, user_id, api_key)
                if candidate_result.success:
                    candidate_result.fallback_used = True
                    candidate_result.fallback_reason = f"OpenRouter Free Router failed ({result.error_code or 'provider_error'}); concrete free candidate streamed successfully: {candidate}"
                    return candidate_result
                last = candidate_result
            return last

        OpenRouterAdapter.call_llm = _call_with_free_cascade
        OpenRouterAdapter.stream_llm = _stream_with_free_cascade
        OpenRouterAdapter._consultaion_free_cascade_installed = True

    _installed = True
