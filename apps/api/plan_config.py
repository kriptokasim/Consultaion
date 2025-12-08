"""
Plan Configuration for Consultaion Billing & Quotas

Defines available subscription plans and their limits.
Payment provider integration deferred to future patchset.

Plans:
- free: Default tier for new users
- pro: Premium tier with higher limits
- internal: For team/admin use with very high limits
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanLimits:
    """Limits and features for a subscription plan."""
    
    daily_token_limit: int
    daily_export_limit: int
    max_concurrent_debates: Optional[int] = None
    features: set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Ensure features is a set."""
        if self.features is None:
            self.features = set()


# Plan definitions
PLANS = {
    "free": PlanLimits(
        daily_token_limit=100_000,  # ~50-100 debate runs depending on complexity
        daily_export_limit=5,        # 5 PDF exports per day
        max_concurrent_debates=1,    # One debate at a time
        features=set(),              # No premium features
    ),
    "pro": PlanLimits(
        daily_token_limit=1_000_000,  # ~500-1000 debates per day
        daily_export_limit=100,       # 100 exports per day
        max_concurrent_debates=5,     # Up to 5 concurrent debates
        features={"conversation_mode", "advanced_models"},
    ),
    "internal": PlanLimits(
        daily_token_limit=10_000_000,  # Effectively unlimited for team use
        daily_export_limit=1000,
        max_concurrent_debates=None,   # No limit
        features={"conversation_mode", "advanced_models", "admin_features"},
    ),
}


def get_plan_limits(plan_name: str) -> PlanLimits:
    """
    Get limits for a plan.
    
    If plan_name is unknown, defaults to 'free' plan.
    This ensures system always has sensible limits even if plan is misconfigured.
    
    Args:
        plan_name: Name of the plan (free/pro/internal)
    
    Returns:
        PlanLimits object with token/export limits and features
    """
    return PLANS.get(plan_name, PLANS["free"])


def resolve_plan_for_user(user: Optional["User"]) -> str:  # noqa: F821
    """
    Resolve plan name for a user.
    
    Rules:
    - If user is None (anonymous): return "free"
    - Otherwise: return user.plan (which defaults to "free" in model)
    
    Args:
        user: User object or None for anonymous users
    
    Returns:
        Plan name string (free/pro/internal)
    """
    if user is None:
        return "free"
    return getattr(user, "plan", "free") or "free"


def list_available_plans() -> list[str]:
    """Get list of all available plan names."""
    return list(PLANS.keys())


def validate_plan(plan_name: str) -> bool:
    """Check if a plan name is valid."""
    return plan_name in PLANS
