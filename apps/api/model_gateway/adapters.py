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
        if model_id == "gpt4o-deep":
            target_model = "openai/gpt-4o"
        elif model_id == "claude-sonnet":
            target_model = "anthropic/claude-3-5-sonnet-20240620"
        elif model_id == "gemini-2-5-pro":
            target_model = "gemini/gemini-2.5-pro-preview-06-05"
        
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
            provider="direct",
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
        target_model = f"openrouter/{model_id}"
        if model_id == "gpt4o-deep":
            target_model = "openrouter/openai/gpt-4o"
        elif model_id == "claude-sonnet":
            target_model = "openrouter/anthropic/claude-3.5-sonnet"
        elif model_id == "gemini-2-5-pro":
            target_model = "openrouter/google/gemini-2.5-pro"
        
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
