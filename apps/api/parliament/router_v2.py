from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from parliament.model_registry import ModelInfo, get_model_info, list_enabled_models
from parliament.provider_health import get_health_state


class RouteContext(BaseModel):
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    requested_model: Optional[str] = None
    routing_policy: Optional[str] = None
    debate_type: Optional[str] = None
    estimated_tokens: Optional[int] = None
    priority: Literal["normal", "high"] = "normal"
    safety_level: Literal["strict", "normal", "relaxed"] = "normal"


class CandidateDecision(BaseModel):
    model: str
    total_score: float
    cost_score: float
    latency_score: float
    quality_score: float
    safety_score: float
    is_healthy: bool
    details: Dict[str, Any] = Field(default_factory=dict)


# Scoring constants
TIER_SCORES = {
    "cost": {"low": 1.0, "medium": 0.5, "high": 0.1},
    "latency": {"fast": 1.0, "normal": 0.5, "slow": 0.1},
    "quality": {"baseline": 0.1, "advanced": 0.6, "flagship": 1.0},
    "safety": {"strict": 1.0, "normal": 0.8, "experimental": 0.5},
}

# Default policy weights
DEFAULT_WEIGHTS = {
    "router-smart": {"quality": 0.4, "cost": 0.3, "latency": 0.2, "safety": 0.1},
    "router-deep": {"quality": 0.8, "cost": 0.1, "latency": 0.05, "safety": 0.05},
}


def _calculate_score(model: ModelInfo, weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    c_score = TIER_SCORES["cost"].get(model.cost_tier, 0.0)
    l_score = TIER_SCORES["latency"].get(model.latency_class, 0.0)
    q_score = TIER_SCORES["quality"].get(model.quality_tier, 0.0)
    s_score = TIER_SCORES["safety"].get(model.safety_profile, 0.0)
    
    total = (
        weights.get("cost", 0) * c_score +
        weights.get("latency", 0) * l_score +
        weights.get("quality", 0) * q_score +
        weights.get("safety", 0) * s_score
    )
    
    details = {
        "cost_raw": c_score,
        "latency_raw": l_score,
        "quality_raw": q_score,
        "safety_raw": s_score,
    }
    return total, details


def choose_model(ctx: RouteContext) -> Tuple[str, List[CandidateDecision]]:
    """
    Choose the best model based on the routing context.
    
    Returns:
        Tuple of (selected_model_id, list_of_candidates)
    """
    # 1. Explicit override
    if ctx.requested_model:
        model = get_model_info(ctx.requested_model)
        if not model or not model.enabled:
            # If requested model is invalid, fall back to smart routing but log it?
            # For now, let's treat it as a hard failure if we can't fulfill the request,
            # OR we can fall back. Given the requirements say "Validate the model",
            # raising an error might be appropriate, but returning a decision with error info is safer.
            # Let's try to return it if it exists in registry even if disabled? No, strict check.
            pass
        else:
            return model.id, [
                CandidateDecision(
                    model=model.id,
                    total_score=1.0,
                    cost_score=0.0,
                    latency_score=0.0,
                    quality_score=0.0,
                    safety_score=0.0,
                    is_healthy=True,
                    details={"reason": "explicit_override"}
                )
            ]

    # 2. Determine policy
    policy_name = ctx.routing_policy or "router-smart"
    if policy_name not in DEFAULT_WEIGHTS:
        policy_name = "router-smart"
    
    weights = DEFAULT_WEIGHTS[policy_name]
    
    # 3. Score candidates
    candidates: List[CandidateDecision] = []
    enabled_models = list_enabled_models()
    
    now = datetime.now(timezone.utc)
    
    for model in enabled_models:
        # Skip router meta-models from being selected as backend targets if they are just aliases
        # But wait, the registry has "router-smart" as a model with provider "openrouter".
        # If the backend supports calling "router-smart" directly (via OpenRouter), we can select it.
        # However, we are implementing the router logic HERE.
        # So we should probably select ACTUAL models (gpt-4o, claude, etc.) and NOT the router aliases,
        # UNLESS the intention is to delegate to OpenRouter's router.
        # The requirements say: "Populate registry with... router-smart, router-deep...".
        # And "Implement a pure-Python function... choose_model".
        # If we select "router-smart", we are delegating routing to OpenRouter.
        # If we select "gpt4o-mini", we are routing locally.
        # The goal is "Make Consultaion a first-class multi-model platform: smarter routing decisions in the backend".
        # This implies WE are doing the routing.
        # So we should prefer concrete models.
        # However, if the user explicitly asks for "router-smart", we might want to use OpenRouter's router.
        # But here we are in the "policy" branch.
        # If policy is "router-smart", we should select the best CONCRETE model based on our scoring.
        # So we should filter out the "router-*" models from the candidates list to avoid recursion or redundancy?
        # Or maybe "router-smart" in registry IS the configuration for the policy?
        # Let's assume we select from concrete models.
        if model.id.startswith("router-"):
            continue
            
        # Check health
        health = get_health_state(model.provider, model.id)
        is_healthy = not health.is_open(now)
        
        # Calculate score
        score, details = _calculate_score(model, weights)
        
        # Apply health penalty
        if not is_healthy:
            score *= 0.1  # Heavy penalty for unhealthy models
            
        candidates.append(CandidateDecision(
            model=model.id,
            total_score=score,
            cost_score=details["cost_raw"],
            latency_score=details["latency_raw"],
            quality_score=details["quality_raw"],
            safety_score=details["safety_raw"],
            is_healthy=is_healthy,
            details=details
        ))
        
    # 4. Sort and select
    if not candidates:
        # Fallback if no candidates (e.g. no models enabled)
        # Should we return the default model from registry?
        from parliament.model_registry import get_default_model
        default = get_default_model()
        return default.id, []

    candidates.sort(key=lambda x: x.total_score, reverse=True)
    
    best_model = candidates[0].model
    return best_model, candidates
