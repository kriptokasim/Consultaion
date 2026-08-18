"""
Static daily quota and feature policy for Consultaion plan slugs.

Paid entitlement is resolved from ``BillingSubscription`` by
``billing.service.get_active_plan``. ``User.plan`` is retained as a legacy/UI
compatibility marker and MUST NOT be used as the authority for paid access.

Plans:
- free: Default tier for new users
- pro: Premium tier with higher limits
- internal: For owner/internal operations
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models import User


@dataclass
class PlanLimits:
    """Static daily limits/features associated with a canonical plan slug."""
    
    daily_token_limit: int
    daily_export_limit: int
    max_concurrent_debates: Optional[int] = None
    features: set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Ensure features is a set."""
        if self.features is None:
            self.features = set()


# Plan definitions. These are daily/runtime policy defaults; billing plan rows
# remain the authority for price, paid entitlement, and configurable limits.
PLANS = {
    "free": PlanLimits(
        daily_token_limit=100_000,  # ~50-100 debate runs depending on complexity
        daily_export_limit=5,
        max_concurrent_debates=1,
        features=set(),
    ),
    "pro": PlanLimits(
        daily_token_limit=1_000_000,
        daily_export_limit=100,
        max_concurrent_debates=5,
        features={"conversation_mode", "advanced_models"},
    ),
    "internal": PlanLimits(
        daily_token_limit=10_000_000,
        daily_export_limit=1000,
        max_concurrent_debates=None,
        features={"conversation_mode", "advanced_models", "admin_features"},
    ),
}


def get_plan_limits(plan_name: str) -> PlanLimits:
    """Return static daily policy for a canonical plan slug.

    Unknown slugs fail safe to the Free policy.
    """
    return PLANS.get(plan_name, PLANS["free"])


def resolve_plan_for_user(user: Optional["User"]) -> str:  # noqa: F821
    """Resolve a user-facing plan slug without making legacy state authoritative.

    When the User instance is attached to the request's SQLModel session, use
    the same canonical ``BillingSubscription`` resolver as authorization. This
    keeps `/me`, login/register responses, and generic user serialization from
    displaying a stale compatibility marker after an entitlement expires or a
    Stripe state transition lands.

    Detached objects and non-request logging paths have no safe database
    context; they retain the legacy marker as a compatibility fallback only.
    """
    if user is None:
        return "free"

    from security.owner import is_owner
    if is_owner(user):
        import logging

        from config import settings
        logging.getLogger(__name__).info(
            "owner_override_applied",
            extra={"user_id": user.id, "email": user.email, "override_type": "plan_marker"},
        )
        return settings.OWNER_PLAN

    # SQLAlchemy can recover the owning request session from an attached ORM
    # instance. SQLModel's Session exposes `.exec`; a plain SQLAlchemy session
    # or detached object safely falls back to the compatibility marker.
    try:
        from sqlalchemy.orm import object_session

        session = object_session(user)
        if session is not None and hasattr(session, "exec"):
            from billing.service import get_active_plan

            return get_active_plan(session, user.id).slug  # type: ignore[arg-type]
    except Exception:
        # Serialization must remain non-fatal if a caller is detached, the
        # session is closing, or billing tables are unavailable during a
        # compatibility/test path. Authorization never uses this fallback.
        pass

    return getattr(user, "plan", "free") or "free"


def list_available_plans() -> list[str]:
    """Get list of all available compatibility plan slugs."""
    return list(PLANS.keys())


def validate_plan(plan_name: str) -> bool:
    """Check if a plan marker slug is valid."""
    return plan_name in PLANS
