import logging
import os
import sys
from model_gateway.types import GatewayRequest, GatewayModelCallResult, GatewayError
from model_gateway.pools import get_model_pool, validate_user_access_to_model, load_pools_config
from model_gateway.costs import check_credit_and_cost_safety
from model_gateway.policy import determine_routing_strategy
from model_gateway.adapters import DirectProviderAdapter, OpenRouterAdapter, MockAdapter
from model_gateway.agent_bridge import call_model_via_gateway

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
            from models import User
            from sqlalchemy.ext.asyncio import AsyncSession
            import asyncio
            
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

    # 1. Validate plan restriction
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
    
    # Log gateway decision
    from model_gateway.observability import log_gateway_decision, log_gateway_call_metrics
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
                
    # Filter the try list to only keep direct models that have their API keys configured
    available_direct_models = []
    for m in models_to_try:
        # Resolve provider
        provider = "unknown"
        if m in MODEL_MAP:
            provider = MODEL_MAP[m]["provider"]
        elif "-" in m:
            provider = m.split("-")[0]
            
        if is_provider_available(provider):
            available_direct_models.append(m)
            
    # If no direct models are available in the pool, fallback to trying the requested model
    if not available_direct_models:
        available_direct_models = [request.model_id]

    last_error = None
    fallback_used = False
    fallback_reason = None
    retry_count = 0
    successful_result = None

    for idx, model_to_call in enumerate(available_direct_models):
        try:
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
            )
            if result.success:
                successful_result = result
                # If we had to switch to an alternative model in the same pool, mark it
                if model_to_call != request.model_id:
                    successful_result.fallback_used = True
                    successful_result.fallback_reason = f"Primary model {request.model_id} failed. Switched to alternative {model_to_call} in same pool."
                break
        except Exception as e:
            logger.warning(f"Direct provider call failed for {model_to_call}: {e}")
            last_error = e
            retry_count += 1

    # Check if we should fall back to OpenRouter
    if not successful_result and (request.gateway_policy in ("auto", "fallback")):
        if is_provider_available("openrouter"):
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
            except Exception as fallback_error:
                logger.error(f"Fallback model gateway route also failed: {fallback_error}")
                last_error = f"Direct failed ({last_error}) and Fallback failed ({fallback_error})"

    # Handle completion or friendly error
    if successful_result:
        successful_result.user_plan = request.user_plan
        log_gateway_call_metrics(successful_result, user_id=request.user_id)
        return successful_result
    else:
        # All failed - friendly error
        logger.error(f"Model gateway call failed. Internal details: {last_error}")
        friendly_error_message = "The model service is temporarily unavailable. Please try again later."
        result = GatewayModelCallResult(
            content="",
            model_used=request.model_id,
            provider="failed",
            success=False,
            error_message=friendly_error_message,
            model_pool=model_pool,
            routing_policy=routing_policy,
            fallback_used=True if fallback_used else False,
            fallback_reason=fallback_reason or "All provider routes failed",
            retry_count=retry_count,
            user_plan=request.user_plan
        )
        log_gateway_call_metrics(result, user_id=request.user_id)
        return result
