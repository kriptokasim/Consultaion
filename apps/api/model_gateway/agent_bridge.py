import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlmodel import Session
from database import engine

logger = logging.getLogger("model_gateway.agent_bridge")

async def call_model_via_gateway(
    *,
    messages: List[Dict[str, str]],
    model_id: str,
    role: str,
    user_id: Optional[str] = None,
    debate_id: Optional[str] = None,
    user_plan: Optional[str] = None,
    gateway_policy: str = "auto",
    temperature: float = 0.3,
    max_tokens: int = 600,
    db_session: Optional[Session] = None,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Any]:
    """
    Unified entry point from Agent execution paths to the central Model Gateway.
    
    Transforms the request parameters into a GatewayRequest, routes the call through
    the policy engine, resolves adapters, measures performance/cost metrics,
    maps successful results to agents.UsageCall, and maps access/quota errors to TransientLLMError
    for graceful runner degradation and UI-facing fail-safes.
    """
    from model_gateway.types import (
        GatewayRequest,
        GatewayQuotaExceededError,
        GatewayModelRestrictedError,
    )
    from model_gateway import route_llm_call
    from agents import UsageCall
    from llm_errors import TransientLLMError

    # 1. Resolve user plan if not explicitly passed
    resolved_user_plan = user_plan
    if not resolved_user_plan and user_id:
        try:
            import asyncio
            from sqlalchemy.ext.asyncio import AsyncSession
            from billing.service import get_active_plan
            if db_session and not isinstance(db_session, AsyncSession):
                plan = get_active_plan(db_session, user_id)
                if plan:
                    resolved_user_plan = plan.name
            else:
                def _get_plan():
                    with Session(engine) as session:
                        plan = get_active_plan(session, user_id)
                        return plan.name if plan else None
                resolved_user_plan = await asyncio.get_running_loop().run_in_executor(None, _get_plan)
        except Exception as e:
            logger.warning(f"Failed to lookup user plan via billing service: {e}")
    
    if not resolved_user_plan:
        resolved_user_plan = "free"

    # 2. Build Request object
    req = GatewayRequest(
        messages=messages,
        model_id=model_id,
        role=role,
        temperature=temperature,
        max_tokens=max_tokens,
        gateway_policy=gateway_policy,
        user_id=user_id,
        user_plan=resolved_user_plan,
        debate_id=debate_id,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
    )

    # 3. Route call through Gateway Orchestrator
    try:
        if db_session:
            gw_res = await route_llm_call(req, db_session=db_session)
        else:
            from database_async import async_session_scope
            async with async_session_scope() as session:
                gw_res = await route_llm_call(req, db_session=session)
    except (GatewayQuotaExceededError, GatewayModelRestrictedError) as e:
        logger.error(f"Gateway access control blocked call: {e}")
        # Map to TransientLLMError so the orchestrator marks the debate as failed
        # and displays the direct access constraint message on the UI.
        raise TransientLLMError(str(e), cause=e)
    except Exception as e:
        logger.error(f"Gateway execution encountered unexpected exception: {e}")
        raise TransientLLMError(f"Gateway routing failed: {e}", cause=e)

    # 4. Check gateway execution success
    if not gw_res.success:
        raise TransientLLMError(
            gw_res.error_message or "LLM response contained no content"
        )

    # 5. Map GatewayModelCallResult back to Agent-compatible UsageCall object
    call_usage = UsageCall(
        prompt_tokens=float(gw_res.prompt_tokens),
        completion_tokens=float(gw_res.completion_tokens),
        total_tokens=float(gw_res.total_tokens),
        cost_usd=gw_res.cost_usd,
        provider=gw_res.provider,
        model=gw_res.model_used,
        gateway=gw_res.gateway,
        model_pool=gw_res.model_pool,
        routing_policy=gw_res.routing_policy,
        fallback_used=gw_res.fallback_used,
        fallback_reason=gw_res.fallback_reason,
        user_plan=gw_res.user_plan,
        estimated_cost_usd=gw_res.estimated_cost_usd,
        retry_count=gw_res.retry_count,
    )

    return gw_res.content, call_usage
