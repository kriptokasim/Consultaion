import time
import asyncio
import logging
from typing import Dict, List, Optional
from litellm import acompletion
from model_gateway.types import GatewayModelCallResult, GatewayError

logger = logging.getLogger("model_gateway.adapters")

class BaseAdapter:
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None
    ) -> GatewayModelCallResult:
        raise NotImplementedError()

class DirectProviderAdapter(BaseAdapter):
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None
    ) -> GatewayModelCallResult:
        # Map model_id to direct provider representation
        target_model = model_id
        provider_name = "direct"
        
        from model_gateway.model_map import MODEL_MAP
        if model_id in MODEL_MAP:
            target_model = MODEL_MAP[model_id]["litellm_model"]
            provider_name = MODEL_MAP[model_id]["provider"]
        else:
            from parliament.model_registry import get_model
            try:
                model_cfg = get_model(model_id)
                if model_cfg:
                    if model_cfg.litellm_model:
                        target_model = model_cfg.litellm_model
                    provider_name = model_cfg.provider
            except Exception:
                if model_id == "gpt4o-deep":
                    target_model = "openai/gpt-4o"
                    provider_name = "openai"
                elif model_id == "claude-sonnet":
                    target_model = "anthropic/claude-3-5-sonnet-20240620"
                    provider_name = "anthropic"
                elif model_id == "gemini-2-5-pro":
                    target_model = "gemini/gemini-2.5-pro-preview-06-05"
                    provider_name = "gemini"

        start_ts = time.monotonic()
        response = await acompletion(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.monotonic() - start_ts) * 1000
        
        content = response.choices[0].message["content"]
        usage = getattr(response, "usage", {}) or {}
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        cost_usd = getattr(response, "response_cost", 0.0) or usage.get("total_cost", 0.0) or 0.0
        
        return GatewayModelCallResult(
            content=content,
            model_used=target_model,
            provider=provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            estimated_cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=True,
            model_pool=model_pool,
            routing_policy=routing_policy,
        )

class OpenRouterAdapter(BaseAdapter):
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None
    ) -> GatewayModelCallResult:
        OPENROUTER_MODEL_MAPPING = {
            "gpt4o-mini": "openrouter/openai/gpt-4o-mini",
            "gpt4o-deep": "openrouter/openai/gpt-4o",
            "claude-sonnet": "openrouter/anthropic/claude-3.5-sonnet",
            "claude-haiku": "openrouter/anthropic/claude-3-haiku",
            "gemini-2-flash": "openrouter/google/gemini-2.0-flash",
            "gemini-2-5-pro": "openrouter/google/gemini-2.5-pro",
            "groq-llama-3-3": "openrouter/meta-llama/llama-3.3-70b-instruct",
            "mistral-large": "openrouter/mistralai/mistral-large",
            "deepseek-r1": "openrouter/deepseek/deepseek-r1",
            "openai_fast": "openrouter/openai/gpt-4o-mini",
            "openai_premium": "openrouter/openai/gpt-4o",
            "anthropic_reasoning": "openrouter/anthropic/claude-3.5-sonnet",
            "gemini_general": "openrouter/google/gemini-2.0-flash",
            "gemini_pro": "openrouter/google/gemini-2.5-pro",
            "groq_fast": "openrouter/meta-llama/llama-3.3-70b-instruct",
            "mistral_large": "openrouter/mistralai/mistral-large",
            "openrouter_fallback": "openrouter/openai/gpt-4o-mini",
            "router-smart": "openrouter/router",
            "router-deep": "openrouter/auto",
        }
        
        target_model = OPENROUTER_MODEL_MAPPING.get(model_id, f"openrouter/{model_id}")
        
        start_ts = time.monotonic()
        response = await acompletion(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.monotonic() - start_ts) * 1000
        
        content = response.choices[0].message["content"]
        usage = getattr(response, "usage", {}) or {}
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        cost_usd = getattr(response, "response_cost", 0.0) or usage.get("total_cost", 0.0) or 0.0
        
        return GatewayModelCallResult(
            content=content,
            model_used=target_model,
            provider="openrouter",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            estimated_cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=True,
            model_pool=model_pool,
            routing_policy=routing_policy,
        )

class MockAdapter(BaseAdapter):
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None
    ) -> GatewayModelCallResult:
        # Fast local mock completion
        await asyncio.sleep(0.05)
        content = f"[Mock response from {model_id}] Received message count: {len(messages)}"
        return GatewayModelCallResult(
            content=content,
            model_used=model_id,
            provider="mock",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.0001,
            estimated_cost_usd=0.0001,
            latency_ms=50.0,
            success=True,
            model_pool=model_pool,
            routing_policy=routing_policy,
        )
