import logging
from model_gateway.types import GatewayRequest, GatewayModelCallResult, GatewayError
from model_gateway.pools import get_model_pool, validate_user_access_to_model
from model_gateway.costs import check_credit_and_cost_safety
from model_gateway.policy import determine_routing_strategy
from model_gateway.adapters import OpenRouterAdapter
from model_gateway.agent_bridge import call_model_via_gateway

logger = logging.getLogger("model_gateway")


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
                if used <= limit:
                    has_credits = True
        except Exception as e:
            logger.warning(f"Error checking hosted credits in gateway: {e}")

    # 1. Validate plan restriction
    validate_user_access_to_model(request.model_id, request.user_plan, has_credits=has_credits)
    
    # 2. Estimate run cost (e.g., standard estimation: 0.015 per 1k input/output tokens)
    # Assume 1000 input, 1000 output tokens for credit check
    estimated_cost_usd = 0.00003 * (len(str(request.messages)) // 4)
    await check_credit_and_cost_safety(request.user_id, request.user_plan, estimated_cost_usd, db_session)
    
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
    
    adapter = adapter_cls()
    fallback_used = False
    fallback_reason = None
    retry_count = 0
    
    try:
        result = await adapter.call_llm(
            messages=request.messages,
            model_id=request.model_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            gateway_policy=request.gateway_policy,
            model_pool=model_pool,
            routing_policy=routing_policy,
            user_id=request.user_id,
        )
        result.user_plan = request.user_plan
        log_gateway_call_metrics(result, user_id=request.user_id)
        return result
    except Exception as primary_error:
        # Fallback trigger: if policy is auto or fallback, retry using OpenRouter
        if request.gateway_policy in ("auto", "fallback"):
            logger.warning(
                f"Primary model gateway route failed: {str(primary_error)}. "
                "Triggering High-Availability Fallback Route..."
            )
            fallback_used = True
            fallback_reason = str(primary_error)
            retry_count = 1
            
            fallback_adapter = OpenRouterAdapter()
            try:
                result = await fallback_adapter.call_llm(
                    messages=request.messages,
                    model_id=request.model_id,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    gateway_policy=request.gateway_policy,
                    model_pool=model_pool,
                    routing_policy=routing_policy + "-fallback",
                    user_id=request.user_id,
                )
                result.fallback_used = True
                result.fallback_reason = fallback_reason
                result.retry_count = retry_count
                result.user_plan = request.user_plan
                log_gateway_call_metrics(result, user_id=request.user_id)
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback model gateway route also failed: {str(fallback_error)}")
                result = GatewayModelCallResult(
                    content="",
                    model_used=request.model_id,
                    provider="failed",
                    success=False,
                    error_message=f"Primary failed ({primary_error}) and Fallback failed ({fallback_error})",
                    model_pool=model_pool,
                    routing_policy=routing_policy,
                    fallback_used=True,
                    fallback_reason=f"Primary: {primary_error} -> Fallback: {fallback_error}",
                    retry_count=retry_count,
                    user_plan=request.user_plan
                )
                log_gateway_call_metrics(result, user_id=request.user_id)
                return result
        
        # If fallback not configured or allowed
        result = GatewayModelCallResult(
            content="",
            model_used=request.model_id,
            provider="failed",
            success=False,
            error_message=str(primary_error),
            model_pool=model_pool,
            routing_policy=routing_policy,
            user_plan=request.user_plan
        )
        log_gateway_call_metrics(result, user_id=request.user_id)
        return result
