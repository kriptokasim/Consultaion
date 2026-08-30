"""Canonical model registry and alias resolution for the Model Gateway."""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger("model_gateway.model_map")
MODEL_MAP: dict[str, dict[str, Any]] = {
    "openai_fast":{"provider":"openai","provider_model_id":"gpt-4o-mini","litellm_model":"openai/gpt-4o-mini","cost_class":"cheap","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "openai_premium":{"provider":"openai","provider_model_id":"gpt-4o","litellm_model":"openai/gpt-4o","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "anthropic_reasoning":{"provider":"anthropic","provider_model_id":"claude-3-5-sonnet-20240620","litellm_model":"anthropic/claude-3-5-sonnet-20240620","cost_class":"paid","deprecated":True,"replacement":"anthropic_reasoning_current","last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":"Legacy durable config; runtime health decides availability."},
    "gemini_general":{"provider":"gemini","provider_model_id":"gemini-3.7-flash","litellm_model":"gemini/gemini-3.7-flash","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":"Google Gemini API","free_tier_limit_notes":"Current production model; availability/pricing is account dependent."},
    "gemini_pro":{"provider":"gemini","provider_model_id":"gemini-3.7-flash","litellm_model":"gemini/gemini-3.7-flash","cost_class":"paid","deprecated":True,"replacement":"gemini_general","last_verified_at":"2026-08-30","free_tier_verified_at":None,"free_tier_source":"Google Gemini API","free_tier_limit_notes":"Legacy preset migrated to current Flash model."},
    "groq_fast":{"provider":"groq","provider_model_id":"openai/gpt-oss-20b","litellm_model":"groq/openai/gpt-oss-20b","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"Groq GPT-OSS 20B","free_tier_limit_notes":"Account/developer-plan limits apply."},
    "deepinfra_reasoning":{"provider":"deepinfra","provider_model_id":"meta-llama/Llama-3.3-70B-Instruct","litellm_model":"deepinfra/meta-llama/Llama-3.3-70B-Instruct","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"DeepInfra free tier","free_tier_limit_notes":"Limited free credits on signup."},
    "together_general":{"provider":"together","provider_model_id":"meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo","litellm_model":"together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"Together AI free tier","free_tier_limit_notes":"Free credits on signup; rate-limited."},
    "fireworks_general":{"provider":"fireworks","provider_model_id":"accounts/fireworks/models/llama-v3p1-8b-instruct","litellm_model":"fireworks_ai/accounts/fireworks/models/llama-v3p1-8b-instruct","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":"2026-06-21","free_tier_source":"Fireworks free tier","free_tier_limit_notes":"Free credits on signup; rate-limited."},
    "perplexity_search":{"provider":"perplexity","provider_model_id":"sonar-reasoning","litellm_model":"perplexity/sonar-reasoning","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "xai_grok":{"provider":"xai","provider_model_id":"grok-2","litellm_model":"xai/grok-2","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "mistral_large":{"provider":"mistral","provider_model_id":"mistral-large-latest","litellm_model":"mistral/mistral-large-latest","cost_class":"paid","deprecated":False,"replacement":None,"last_verified_at":"2026-06-21","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
    "openrouter_fallback":{"provider":"openrouter","provider_model_id":"openrouter/free","litellm_model":"openrouter/openrouter/free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter Free Router","free_tier_limit_notes":"Selects from currently available free endpoints; rate limited."},
    "router-smart":{"provider":"openrouter","provider_model_id":"openrouter/free","litellm_model":"openrouter/openrouter/free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter Free Router","free_tier_limit_notes":"Dynamic upstream selection."},
    "router-deep":{"provider":"openrouter","provider_model_id":"z-ai/glm-5.2:free","litellm_model":"openrouter/z-ai/glm-5.2:free","cost_class":"free","deprecated":False,"replacement":None,"last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Free endpoint; rate limited."},
    "llama-3-free":{"provider":"openrouter","provider_model_id":"openai/gpt-oss-20b:free","litellm_model":"openrouter/openai/gpt-oss-20b:free","cost_class":"free","deprecated":True,"replacement":"openrouter_fallback","last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Legacy key retained for persisted panels."},
    "mimo-v2-free":{"provider":"openrouter","provider_model_id":"openai/gpt-oss-20b:free","litellm_model":"openrouter/openai/gpt-oss-20b:free","cost_class":"free","deprecated":True,"replacement":"openrouter_fallback","last_verified_at":"2026-08-30","free_tier_verified_at":"2026-08-30","free_tier_source":"OpenRouter","free_tier_limit_notes":"Legacy key retained for persisted panels."},
    "deepseek-r1":{"provider":"openrouter","provider_model_id":"deepseek/deepseek-r1","litellm_model":"openrouter/deepseek/deepseek-r1","cost_class":"medium","deprecated":False,"replacement":None,"last_verified_at":"2026-06-28","free_tier_verified_at":None,"free_tier_source":None,"free_tier_limit_notes":None},
}
MODEL_ALIASES: dict[str,str] = {"gpt4o-mini":"openai_fast","gpt4o-deep":"openai_premium","claude-sonnet":"anthropic_reasoning","claude-haiku":"anthropic_reasoning","gemini-2-flash":"gemini_general","gemini-2-5-pro":"gemini_pro","groq-llama-3-3":"groq_fast","mistral-large":"mistral_large","gpt-4o-mini":"openai_fast","gpt-4.1-mini":"openai_fast","gpt-4o":"openai_premium","claude-3-5-sonnet":"anthropic_reasoning","claude-3-5-haiku":"anthropic_reasoning","gemini-1.5-flash":"gemini_general","gemini-1.5-pro":"gemini_pro","openai/gpt-4o-mini":"openai_fast","openai/gpt-4o":"openai_premium","anthropic/claude-3-5-sonnet-20240620":"anthropic_reasoning","anthropic/claude-3-haiku-20240307":"anthropic_reasoning","gemini/gemini-2.0-flash":"gemini_general","gemini/gemini-2.5-pro-preview-06-05":"gemini_pro","groq/llama-3.3-70b-versatile":"groq_fast","mistral/mistral-large-latest":"mistral_large","openrouter/deepseek/deepseek-r1":"deepseek-r1"}
class ModelKeyError(Exception): pass
def resolve_model_key(model_key:str)->str:
    if model_key in MODEL_MAP: return model_key
    canonical=MODEL_ALIASES.get(model_key)
    if canonical is not None:
        logger.warning("Deprecated model alias '%s' used — resolved to '%s'.",model_key,canonical); return canonical
    raise ModelKeyError(f"Unknown model key '{model_key}'. Valid canonical keys: {sorted(MODEL_MAP.keys())}.")
def get_model_cost_class(model_key:str)->str: return MODEL_MAP.get(model_key,{}).get("cost_class","unknown")
def is_free_model(model_key:str)->bool: return get_model_cost_class(model_key)=="free"

# The gateway historically passed the primary canonical model id into the
# OpenRouter fallback adapter. That caused a failed Gemini/OpenAI/Groq model to
# be retried on OpenRouter under the wrong upstream slug. Keep the adapter API
# stable while making gateway_policy="fallback" authoritative.
def _install_fallback_model_guard() -> None:
    try:
        from model_gateway.adapters import OpenRouterAdapter
    except Exception:
        return
    if getattr(OpenRouterAdapter, "_consultaion_free_fallback_guard", False):
        return
    original_resolve = OpenRouterAdapter._resolve_model
    original_call = OpenRouterAdapter.call_llm
    original_stream = OpenRouterAdapter.stream_llm
    def _resolve(model_id: str) -> str:
        if model_id == "__consultaion_free_fallback__":
            return MODEL_MAP["openrouter_fallback"]["litellm_model"]
        return original_resolve(model_id)
    async def _call(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, user_id=None, response_format=None, tools=None, tool_choice=None, api_key=None):
        if gateway_policy == "fallback": model_id = "__consultaion_free_fallback__"
        return await original_call(self,messages,model_id,temperature,max_tokens,gateway_policy,model_pool,routing_policy,user_id,response_format,tools,tool_choice,api_key)
    async def _stream(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, on_delta, user_id=None, api_key=None):
        if gateway_policy == "fallback": model_id = "__consultaion_free_fallback__"
        return await original_stream(self,messages,model_id,temperature,max_tokens,gateway_policy,model_pool,routing_policy,on_delta,user_id,api_key)
    OpenRouterAdapter._resolve_model = staticmethod(_resolve)
    OpenRouterAdapter.call_llm = _call
    OpenRouterAdapter.stream_llm = _stream
    OpenRouterAdapter._consultaion_free_fallback_guard = True
_install_fallback_model_guard()
