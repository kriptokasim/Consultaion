import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from litellm import acompletion
from llm_errors import classify_provider_exception

from model_gateway.types import GatewayModelCallResult, ModelDelta, OnDeltaCallback

logger = logging.getLogger("model_gateway.adapters")

class BaseAdapter(ABC):
    @abstractmethod
    async def stream_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        on_delta: OnDeltaCallback,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult: ...

    @abstractmethod
    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult: ...

class DirectProviderAdapter(BaseAdapter):
    async def stream_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        on_delta: OnDeltaCallback,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult:
        from model_gateway.model_map import MODEL_MAP
        target_model = model_id
        provider_name = "direct"

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
                pass

        start_ts = time.monotonic()
        accumulated = ""
        seq = 0
        ttft_ms: float | None = None

        from config import settings
        first_token_timeout_s = getattr(settings, "ARENA_FIRST_TOKEN_TIMEOUT_MS", 15000) / 1000.0
        active_stream_timeout_s = getattr(settings, "ARENA_ACTIVE_STREAM_TIMEOUT_MS", 30000) / 1000.0
        total_timeout_s = getattr(settings, "ARENA_STREAM_TOTAL_TIMEOUT_MS", 60000) / 1000.0

        try:
            llm_kwargs: dict[str, Any] = {}
            if api_key:
                llm_kwargs["api_key"] = api_key
            response = await acompletion(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **llm_kwargs,
            )
            response_aiter = response.__aiter__()
            while True:
                now = time.monotonic()
                total_elapsed = now - start_ts
                if total_elapsed >= total_timeout_s:
                    raise asyncio.TimeoutError("stream_total_timeout")

                if ttft_ms is None:
                    timeout_for_chunk = min(first_token_timeout_s, total_timeout_s - total_elapsed)
                else:
                    timeout_for_chunk = min(active_stream_timeout_s, total_timeout_s - total_elapsed)

                if timeout_for_chunk <= 0:
                    raise asyncio.TimeoutError("stream_total_timeout")

                try:
                    chunk = await asyncio.wait_for(response_aiter.__anext__(), timeout=timeout_for_chunk)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    if ttft_ms is None:
                        raise asyncio.TimeoutError("stream_first_token_timeout")
                    else:
                        raise asyncio.TimeoutError("stream_active_stall")

                delta = chunk.choices[0].delta if chunk.choices else None
                text = getattr(delta, "content", None) or "" if delta else ""
                if text:
                    now = time.monotonic()
                    if ttft_ms is None:
                        ttft_ms = (now - start_ts) * 1000
                    accumulated += text
                    seq += 1
                    await on_delta(ModelDelta(text=text, sequence=seq, accumulated_chars=len(accumulated)))
        except NotImplementedError:
            # Provider doesn't support streaming — fall back to non-streaming
            result = await self.call_llm(
                messages, model_id, temperature, max_tokens,
                gateway_policy, model_pool, routing_policy, user_id,
                api_key=api_key,
            )
            return result
        except asyncio.TimeoutError as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            err_code = str(e) if str(e) in ("stream_first_token_timeout", "stream_active_stall", "stream_total_timeout") else "stream_total_timeout"
            return GatewayModelCallResult(
                content=accumulated,
                model_used=target_model,
                provider=provider_name,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                success=False,
                error_message=f"Streaming timeout ({err_code})",
                error_code=err_code,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            failure = classify_provider_exception(e)
            return GatewayModelCallResult(
                content=accumulated,
                model_used=target_model,
                provider=provider_name,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                success=False,
                error_message=failure.message,
                error_code=failure.code.value,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )

        latency_ms = (time.monotonic() - start_ts) * 1000
        return GatewayModelCallResult(
            content=accumulated,
            model_used=target_model,
            provider=provider_name,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            success=True,
            model_pool=model_pool,
            routing_policy=routing_policy,
        )

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
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
        kwargs = {}
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if api_key is not None:
            kwargs["api_key"] = api_key

        try:
            response = await acompletion(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            failure = classify_provider_exception(e)
            logger.warning(f"DirectProviderAdapter error calling {target_model}: {failure.raw_error}")
            return GatewayModelCallResult(
                content="",
                model_used=target_model,
                provider=provider_name,
                latency_ms=latency_ms,
                success=False,
                error_message=failure.message,
                error_code=failure.code.value,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )

        latency_ms = (time.monotonic() - start_ts) * 1000
        
        tool_calls = getattr(response.choices[0].message, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            content = tool_calls[0].function.arguments
        else:
            content = response.choices[0].message.get("content") or ""
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
    """Adapter that routes all calls through OpenRouter."""

    # ── Static fallback mapping (used when model_id is NOT in MODEL_MAP) ──
    _STATIC_MAPPING: Dict[str, str] = {
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
    }

    @staticmethod
    def _resolve_model(model_id: str) -> str:
        """Resolve model_id to an OpenRouter-prefixed litellm model string.

        Priority: MODEL_MAP litellm_model → static fallback → f"openrouter/{model_id}".
        """
        from model_gateway.model_map import MODEL_MAP
        record = MODEL_MAP.get(model_id)
        if record and record.get("provider") == "openrouter":
            return record["litellm_model"]
        if model_id in OpenRouterAdapter._STATIC_MAPPING:
            return OpenRouterAdapter._STATIC_MAPPING[model_id]
        # Last resort: prefix with openrouter/
        if model_id.startswith("openrouter/"):
            return model_id
        return f"openrouter/{model_id}"

    async def stream_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        on_delta: OnDeltaCallback,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult:
        target_model = self._resolve_model(model_id)

        start_ts = time.monotonic()
        accumulated = ""
        seq = 0
        ttft_ms: float | None = None

        from config import settings
        first_token_timeout_s = getattr(settings, "ARENA_FIRST_TOKEN_TIMEOUT_MS", 15000) / 1000.0
        active_stream_timeout_s = getattr(settings, "ARENA_ACTIVE_STREAM_TIMEOUT_MS", 30000) / 1000.0
        total_timeout_s = getattr(settings, "ARENA_STREAM_TOTAL_TIMEOUT_MS", 60000) / 1000.0

        try:
            llm_kwargs = {}
            if api_key:
                llm_kwargs["api_key"] = api_key
            response = await acompletion(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **llm_kwargs
            )
            response_aiter = response.__aiter__()
            while True:
                now = time.monotonic()
                total_elapsed = now - start_ts
                if total_elapsed >= total_timeout_s:
                    raise asyncio.TimeoutError("stream_total_timeout")

                if ttft_ms is None:
                    timeout_for_chunk = min(first_token_timeout_s, total_timeout_s - total_elapsed)
                else:
                    timeout_for_chunk = min(active_stream_timeout_s, total_timeout_s - total_elapsed)

                if timeout_for_chunk <= 0:
                    raise asyncio.TimeoutError("stream_total_timeout")

                try:
                    chunk = await asyncio.wait_for(response_aiter.__anext__(), timeout=timeout_for_chunk)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    if ttft_ms is None:
                        raise asyncio.TimeoutError("stream_first_token_timeout")
                    else:
                        raise asyncio.TimeoutError("stream_active_stall")

                delta = chunk.choices[0].delta if chunk.choices else None
                text = getattr(delta, "content", None) or "" if delta else ""
                if text:
                    now = time.monotonic()
                    if ttft_ms is None:
                        ttft_ms = (now - start_ts) * 1000
                    accumulated += text
                    seq += 1
                    await on_delta(ModelDelta(text=text, sequence=seq, accumulated_chars=len(accumulated)))
        except NotImplementedError:
            result = await self.call_llm(
                messages, model_id, temperature, max_tokens,
                gateway_policy, model_pool, routing_policy, user_id,
                api_key=api_key,
            )
            return result
        except asyncio.TimeoutError as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            err_code = str(e) if str(e) in ("stream_first_token_timeout", "stream_active_stall", "stream_total_timeout") else "stream_total_timeout"
            return GatewayModelCallResult(
                content=accumulated,
                model_used=target_model,
                provider="openrouter",
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                success=False,
                error_message=f"Streaming timeout ({err_code})",
                error_code=err_code,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            failure = classify_provider_exception(e)
            return GatewayModelCallResult(
                content=accumulated,
                model_used=target_model,
                provider="openrouter",
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                success=False,
                error_message=failure.message,
                error_code=failure.code.value,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )

        latency_ms = (time.monotonic() - start_ts) * 1000
        return GatewayModelCallResult(
            content=accumulated,
            model_used=target_model,
            provider="openrouter",
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            success=True,
            model_pool=model_pool,
            routing_policy=routing_policy,
        )

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult:
        target_model = self._resolve_model(model_id)
        
        start_ts = time.monotonic()
        kwargs = {}
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if api_key is not None:
            kwargs["api_key"] = api_key

        try:
            response = await acompletion(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_ts) * 1000
            failure = classify_provider_exception(e)
            logger.warning(f"OpenRouterAdapter error calling {target_model}: {failure.raw_error}")
            return GatewayModelCallResult(
                content="",
                model_used=target_model,
                provider="openrouter",
                latency_ms=latency_ms,
                success=False,
                error_message=failure.message,
                error_code=failure.code.value,
                model_pool=model_pool,
                routing_policy=routing_policy,
            )

        latency_ms = (time.monotonic() - start_ts) * 1000
        
        tool_calls = getattr(response.choices[0].message, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            content = tool_calls[0].function.arguments
        else:
            content = response.choices[0].message.get("content") or ""
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
    async def stream_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        on_delta: OnDeltaCallback,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> GatewayModelCallResult:
        await asyncio.sleep(0.05)
        content = f"[Mock response from {model_id}] Received message count: {len(messages)}"
        await on_delta(ModelDelta(text=content, sequence=0, accumulated_chars=len(content)))
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

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float,
        max_tokens: int,
        gateway_policy: str,
        model_pool: str,
        routing_policy: str,
        user_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
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
