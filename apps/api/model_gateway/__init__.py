import logging
import os

from model_gateway.adapters import DirectProviderAdapter, MockAdapter, OpenRouterAdapter
from model_gateway.agent_bridge import call_model_via_gateway
from model_gateway.costs import check_credit_and_cost_safety
from model_gateway.model_map import ModelKeyError, is_free_model, resolve_model_key
from model_gateway.policy import determine_routing_strategy
from model_gateway.pools import get_model_pool, load_pools_config, validate_user_access_to_model
from model_gateway.types import (
    GatewayError,
    GatewayModelCallResult,
    GatewayModelRestrictedError,
    GatewayRequest,
)

logger = logging.getLogger("model_gateway")

def is_provider_available(provider: str) -> bool:
    from config import settings
    if settings.USE_MOCK:
        return True
    key_name = f"{provider.upper()}_API_KEY"
    if provider == "gemini":
        return bool(getattr(settings, "GEMINI_API_KEY", None) or getattr(settings, "GOOGLE_API_KEY", None))
    return bool(getattr(settings, key_name, None))

def export_api_keys():
    from config import settings
    mappings = {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "GEMINI_API_KEY": settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY,
        "GOOGLE_API_KEY": settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY,
        "GROQ_API_KEY": settings.GROQ_API_KEY,
        "DEEPINFRA_API_KEY": settings.DEEPINFRA_API_KEY,
        "TOGETHER_API_KEY": settings.TOGETHER_API_KEY,
        "TOGETHERAI_API_KEY": settings.TOGETHER_API_KEY,
        "FIREWORKS_API_KEY": settings.FIREWORKS_API_KEY,
        "MISTRAL_API_KEY": settings.MISTRAL_API_KEY,
        "XAI_API_KEY": settings.XAI_API_KEY,
        "PERPLEXITY_API_KEY": settings.PERPLEXITY_API_KEY,
        "OPENROUTER_API_KEY": settings.OPENROUTER_API_KEY,
    }
    for k, v in mappings.items():
        if v:
            os.environ[k] = v

async def route_llm_call(
    request: GatewayRequest,
    db_session = None
) -> GatewayModelCallResult:
    """The central router routing incoming LLM calls through the Model Gateway."""
    # 1. Check user hosted credits to bypass Pro pool restriction
    has_credits = False
    if db_session and request.user_id:
        try:
            import asyncio

            from models import User
            from sqlalchemy.ext.asyncio import AsyncSession
            
            if isinstance(db_session, AsyncSession):
                user = await db_session.get(User, request.user_id)
            else:
                def _get_user():
                    return db_session.get(User, request.user_id)
                user = await asyncio.get_running_loop().run_in_executor(None, _get_user)
                
            if user:
                limit = getattr(user, "hosted_credits_limit", 10)
                used = getattr(user, "hosted_credits_used", 0)
                if used < limit:
                    has_credits = True
        except Exception as e:
            logger.warning(f"Error checking hosted credits in gateway: {e}")

    # 1. Resolve canonical model key
    from config import settings

    from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP
    # Diagnostic: log model resolution context before attempt
    logger.info(
        "model_gateway.resolve_attempt",
        extra={
            "requested_model_id": request.model_id,
            "in_model_map": request.model_id in MODEL_MAP,
            "in_aliases": request.model_id in MODEL_ALIASES,
            "user_id": request.user_id,
            "user_plan": request.user_plan,
            "gateway_policy": request.gateway_policy,
        },
    )
    try:
        resolved_model_id = resolve_model_key(request.model_id)
    except ModelKeyError as mke:
        logger.error(
            "model_gateway.model_key_unresolved",
            extra={
                "requested_model_id": request.model_id,
                "error": str(mke),
                "user_id": request.user_id,
            },
        )
        # Return a structured error result with safe failure code
        return GatewayModelCallResult(
            content="",
            model_used=request.model_id,
            provider="gateway",
            success=False,
            error_message=(
                f'The selected model "{request.model_id}" is not available. '
                "Please choose a supported model or retry with default models."
            ),
            error_code="model_key_unresolved",
            model_pool="default",
            routing_policy="resolve",
        )
    request.model_id = resolved_model_id  # ensure downstream components use canonical key

    # 1a. Free-only mode guard
    if settings.FREE_ONLY_MODE and not is_free_model(resolved_model_id):
        logger.warning(f"FREE_ONLY_MODE block: {resolved_model_id} is not explicitly free")
        raise GatewayModelRestrictedError(f"Model '{resolved_model_id}' is not available in free-only mode.")

    # 1b. Validate plan restriction
    validate_user_access_to_model(request.model_id, request.user_plan, has_credits=has_credits)
    
    # 2. Estimate run cost (e.g., standard estimation: 0.015 per 1k input/output tokens)
    # Assume 1000 input, 1000 output tokens for credit check
    estimated_cost_usd = 0.00003 * (len(str(request.messages)) // 4)
    await check_credit_and_cost_safety(request.user_id, request.user_plan, estimated_cost_usd, db_session)
    
    # Export keys to environment for LiteLLM
    export_api_keys()
    

    
    # 3. Determine routing strategy
    adapter_cls, routing_policy = determine_routing_strategy(request)
    model_pool = get_model_pool(request.model_id)
    
    # Patchset 136: Gateway call started metric
    try:
        from metrics import incr_metric
        incr_metric("model_gateway.call.started")
    except Exception:
        pass
    
    # Log gateway decision
    from model_gateway.observability import log_gateway_call_metrics, log_gateway_decision
    from model_gateway.types import GatewayDecision
    decision = GatewayDecision(
        selected_model=request.model_id,
        selected_provider=adapter_cls.__name__,
        policy_used=routing_policy,
        model_pool=model_pool,
        estimated_cost_usd=estimated_cost_usd,
        fallback_enabled=(request.gateway_policy in ("auto", "fallback")),
    )
    log_gateway_decision(decision, user_id=request.user_id)
    
    # If using MockAdapter (testing environment), bypass loop
    if adapter_cls == MockAdapter:
        try:
            adapter = MockAdapter()
            result = await adapter.call_llm(
                messages=request.messages,
                model_id=request.model_id,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                gateway_policy=request.gateway_policy,
                model_pool=model_pool,
                routing_policy=routing_policy,
                user_id=request.user_id,
                response_format=request.response_format,
                tools=request.tools,
                tool_choice=request.tool_choice,
            )
            result.user_plan = request.user_plan
            log_gateway_call_metrics(result, user_id=request.user_id)
            return result
        except Exception as mock_error:
            result = GatewayModelCallResult(
                content="",
                model_used=request.model_id,
                provider="mock",
                success=False,
                error_message=str(mock_error),
                model_pool=model_pool,
                routing_policy=routing_policy,
                user_plan=request.user_plan
            )
            log_gateway_call_metrics(result, user_id=request.user_id)
            return result

    # Resolve all direct models to try in the pool
    # First: the requested model itself
    models_to_try = [request.model_id]
    
    # Second: other direct models in the same pool
    from model_gateway.model_map import MODEL_MAP
    pool_models = []
    config = load_pools_config()
    pools = config.get("pools", {})
    if model_pool in pools:
        pool_models = pools[model_pool].get("models", [])
        
    for m in pool_models:
        # Check if it is a direct provider (i.e. mapped in MODEL_MAP and provider != "openrouter")
        if m in MODEL_MAP and MODEL_MAP[m]["provider"] != "openrouter":
            if m not in models_to_try:
                models_to_try.append(m)
                
    # Pass all candidates to the adapter loop; BYOK resolution or server key checks will happen there.
    available_direct_models = models_to_try

    last_error = None
    last_error_code = None
    fallback_used = False
    fallback_reason = None
    retry_count = 0
    successful_result = None

    # Filter out models with open circuits
    from model_gateway.provider_health import is_circuit_open, record_failure, record_success
    from model_gateway.policy import _model_uses_openrouter
    filtered_direct_models = []
    for m in available_direct_models:
        # Resolve provider
        provider = "unknown"
        if _model_uses_openrouter(m) or m.startswith("openrouter/"):
            provider = "openrouter"
        elif m in MODEL_MAP:
            provider = MODEL_MAP[m]["provider"]
        elif "-" in m:
            provider = m.split("-")[0]
            
        if is_circuit_open(provider):
            last_error = f"Circuit open for provider: {provider}"
            last_error_code = "no_healthy_provider_route"
        else:
            filtered_direct_models.append(m)

    for idx, model_to_call in enumerate(filtered_direct_models):
        # Resolve provider
        provider = "unknown"
        if _model_uses_openrouter(model_to_call) or model_to_call.startswith("openrouter/"):
            provider = "openrouter"
        elif model_to_call in MODEL_MAP:
            provider = MODEL_MAP[model_to_call]["provider"]
        elif "-" in model_to_call:
            provider = model_to_call.split("-")[0]

        # Patchset 136: Provider attempted metric
        try:
            from metrics import incr_metric
            incr_metric("model_gateway.provider.attempted", tags={"provider": provider})
        except Exception:
            pass

        # Resolve user BYOK credential specifically for this provider
        current_api_key = None
        if db_session and request.user_id:
            try:
                from sqlalchemy.ext.asyncio import AsyncSession
                if isinstance(db_session, AsyncSession):
                    from services.provider_credentials import get_model_api_key_async
                    resolved = await get_model_api_key_async(db_session, request.user_id, provider)
                else:
                    import asyncio

                    from services.provider_credentials import get_model_api_key
                    def _get_key(p=provider):
                        return get_model_api_key(db_session, request.user_id, p)
                    resolved = await asyncio.get_running_loop().run_in_executor(None, _get_key)
                
                if resolved and resolved.source == "user":
                    current_api_key = resolved.key
                    logger.info("Using user BYOK key for provider=%s model=%s user=%s", provider, model_to_call, request.user_id)
            except Exception as e:
                logger.warning(f"Failed to lookup BYOK key for provider {provider}: {e}")

        if provider == "openrouter" and not current_api_key:
            from config import settings as _settings
            current_api_key = _settings.OPENROUTER_API_KEY or None

        try:
            # Use the correct adapter for the resolved provider
            if provider == "openrouter":
                adapter = OpenRouterAdapter()
            else:
                adapter = DirectProviderAdapter()
            result = await adapter.call_llm(
                messages=request.messages,
                model_id=model_to_call,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                gateway_policy=request.gateway_policy,
                model_pool=model_pool,
                routing_policy=routing_policy,
                user_id=request.user_id,
                response_format=request.response_format,
                tools=request.tools,
                tool_choice=request.tool_choice,
                api_key=current_api_key,
            )
            if result.success:
                successful_result = result
                record_success(provider)
                # Patchset 136: Provider success metric
                try:
                    from metrics import incr_metric
                    incr_metric("model_gateway.provider.success", tags={"provider": provider})
                except Exception:
                    pass
                # If we had to switch to an alternative model in the same pool, mark it
                if model_to_call != request.model_id:
                    successful_result.fallback_used = True
                    successful_result.fallback_reason = f"Primary model {request.model_id} failed. Switched to alternative {model_to_call} in same pool."
                break
            else:
                last_error = result.error_message
                last_error_code = result.error_code
                record_failure(provider, result.error_code or "unknown", result.error_message or "")
                # Patchset 136: Provider failed metric
                try:
                    from metrics import incr_metric
                    incr_metric("model_gateway.provider.failed", tags={"provider": provider})
                except Exception:
                    pass
                retry_count += 1
        except Exception as e:
            logger.warning(f"Direct provider call failed for {model_to_call}: {e}")
            last_error = str(e)
            last_error_code = "unknown"
            record_failure(provider, "unknown", str(e))
            retry_count += 1

    # Check if we should fall back to OpenRouter
    if not successful_result and (request.gateway_policy in ("auto", "fallback")):
        if is_provider_available("openrouter"):
            if is_circuit_open("openrouter"):
                last_error = "OpenRouter circuit is open. Fallback route bypassed."
                last_error_code = "no_healthy_provider_route"
            else:
                logger.warning(
                    f"All direct provider routes failed. Last error: {last_error}. "
                    "Triggering OpenRouter Fallback Route..."
                )
                fallback_used = True
                fallback_reason = f"All direct models failed. Last error: {last_error}"
                
                try:
                    fallback_adapter = OpenRouterAdapter()
                    result = await fallback_adapter.call_llm(
                        messages=request.messages,
                        model_id="openrouter_fallback",
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        gateway_policy=request.gateway_policy,
                        model_pool=model_pool,
                        routing_policy=routing_policy + "-fallback",
                        user_id=request.user_id,
                        response_format=request.response_format,
                        tools=request.tools,
                        tool_choice=request.tool_choice,
                    )
                    if result.success:
                        successful_result = result
                        successful_result.fallback_used = True
                        successful_result.fallback_reason = fallback_reason
                        successful_result.retry_count = retry_count
                        record_success("openrouter")
                    else:
                        last_error = result.error_message
                        last_error_code = result.error_code
                        record_failure("openrouter", result.error_code or "unknown", result.error_message or "")
                        last_error_reason = f"Direct failed ({last_error}) and Fallback failed ({result.error_message})"
                except Exception as fallback_error:
                    logger.error(f"Fallback model gateway route also failed: {fallback_error}")
                    last_error = f"Direct failed ({last_error}) and Fallback failed ({fallback_error})"
                    last_error_code = "unknown"
                    record_failure("openrouter", "unknown", str(fallback_error))

    # Handle completion or friendly error
    if successful_result:
        successful_result.user_plan = request.user_plan
        log_gateway_call_metrics(successful_result, user_id=request.user_id)
        return successful_result
    else:
        # All failed - friendly error
        logger.error(f"Model gateway call failed. Internal details: {last_error}")
        friendly_error_message = last_error or "The model service is temporarily unavailable. Please try again later."
        result = GatewayModelCallResult(
            content="",
            model_used=request.model_id,
            provider="failed",
            success=False,
            error_message=friendly_error_message,
            error_code=last_error_code or "unknown",
            model_pool=model_pool,
            routing_policy=routing_policy,
            fallback_used=True if fallback_used else False,
            fallback_reason=fallback_reason or "All provider routes failed",
            retry_count=retry_count,
            user_plan=request.user_plan
        )
        log_gateway_call_metrics(result, user_id=request.user_id)
        return result


async def route_llm_stream(
    *,
    messages: list[dict[str, str]],
    model_id: str,
    temperature: float = 0.7,
    max_tokens: int = 1200,
    on_delta=None,
    debate_id: str | None = None,
    user_id: str | None = None,
) -> GatewayModelCallResult:
    """Stream LLM tokens via the gateway, calling on_delta for each chunk.

    Simpler than route_llm_call — no quota checks, no fallback chains.
    Used by the arena streaming path (FH101/FH102).
    """
    from model_gateway.provider_health import is_circuit_open, record_failure, record_success

    export_api_keys()

    adapter_cls: type = DirectProviderAdapter
    provider = "direct"

    # Use policy._model_uses_openrouter — it checks the parliament registry
    # in addition to MODEL_MAP, so free-tier models (llama-3-free, mimo-v2-free)
    # that live in the registry but not MODEL_MAP are correctly detected.
    from model_gateway.policy import _model_uses_openrouter
    from model_gateway.model_map import MODEL_MAP
    if _model_uses_openrouter(model_id) or model_id.startswith("openrouter/"):
        adapter_cls = OpenRouterAdapter
        provider = "openrouter"
    elif model_id in MODEL_MAP:
        provider = MODEL_MAP[model_id]["provider"]

    if is_circuit_open(provider):
        return GatewayModelCallResult(
            content="",
            model_used=model_id,
            provider=provider,
            success=False,
            error_message=f"Provider {provider} circuit is open.",
            error_code="no_healthy_provider_route",
            model_pool="default",
            routing_policy="stream",
        )

    api_key = None
    if user_id:
        try:
            from database_async import async_session_scope
            from services.provider_credentials import get_model_api_key_async
            async with async_session_scope() as session:
                resolved = await get_model_api_key_async(session, user_id, provider)
                if resolved:
                    api_key = resolved.key
        except Exception as e:
            logger.warning(f"Failed to resolve api key in stream: {e}")

    # Server-key fallback: if no BYOK key resolved and provider is OpenRouter,
    # use the server's OpenRouter API key
    if provider == "openrouter" and not api_key:
        from config import settings as _settings
        api_key = _settings.OPENROUTER_API_KEY or None

    adapter = adapter_cls()
    result = await adapter.stream_llm(
        messages=messages,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        gateway_policy="auto",
        model_pool="default",
        routing_policy="stream",
        on_delta=on_delta or (lambda d: None),
        user_id=user_id,
        api_key=api_key,
    )

    if result.success:
        record_success(provider)
    else:
        record_failure(provider, result.error_code or "unknown", result.error_message or "")

    return result


__all__ = [
    "DirectProviderAdapter",
    "MockAdapter",
    "OpenRouterAdapter",
    "call_model_via_gateway",
    "check_credit_and_cost_safety",
    "determine_routing_strategy",
    "get_model_pool",
    "load_pools_config",
    "validate_user_access_to_model",
    "GatewayError",
    "GatewayModelCallResult",
    "GatewayRequest",
    "is_provider_available",
    "export_api_keys",
    "route_llm_call",
    "route_llm_stream",
]
