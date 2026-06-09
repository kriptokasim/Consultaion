"""LLM action guard — rate limit + credit + access checks for expensive endpoints.

Usage:
    from guards.llm_action_guard import require_llm_action_allowed

    @router.post("/oracle")
    async def start_oracle(
        ...,
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        require_llm_action_allowed(
            user=current_user,
            action="oracle_session",
            session=session,
        )
        ...
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from exceptions import PermissionError, RateLimitError, ValidationError
from models import Debate, User
from ratelimit import increment_ip_bucket
from sqlmodel import Session

logger = logging.getLogger(__name__)

# Per-action rate limits: (window_seconds, max_requests)
ACTION_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "arena_run":           (60, 5),
    "debate_run":          (60, 5),
    "oracle_session":      (300, 3),
    "oracle_fork":         (120, 5),
    "redteam_session":     (300, 3),
    "challenge_round":     (60, 10),
    "divergence_recompute": (60, 10),
    "voting_prediction":   (60, 20),
}

# Simple per-user in-memory cooldown tracker (resets on process restart)
_user_last_action: dict[str, dict[str, float]] = {}


def require_llm_action_allowed(
    *,
    user: User,
    action: str,
    session: Session,
    debate_id: Optional[str] = None,
    estimated_cost_units: int = 1,
    ip_address: str = "0.0.0.0",
) -> None:
    """Enforce rate limit, quota, and access checks for LLM-triggering actions.

    Raises RateLimitError, ValidationError, or PermissionError on failure.
    """
    # 1. Account active check
    if not user.is_active:
        raise PermissionError(
            message="Account is not active",
            code="llm.account_inactive",
        )

    # 2. Per-action rate limit
    window, max_requests = ACTION_RATE_LIMITS.get(action, (60, 10))
    allowed, retry_after = increment_ip_bucket(
        ip=ip_address,
        window_seconds=window,
        max_requests=max_requests,
        user_id=user.id,
    )
    if not allowed:
        raise RateLimitError(
            message=f"Too many {action} requests. Please wait before trying again.",
            code="llm.rate_limited",
            retry_after_seconds=retry_after,
            details={"action": action, "retry_after": retry_after},
        )

    # 3. Per-user cooldown (minimum seconds between same action)
    now = time.time()
    user_actions = _user_last_action.setdefault(user.id, {})
    last_time = user_actions.get(action, 0.0)
    cooldown = 2.0  # minimum 2s between same action
    if now - last_time < cooldown:
        raise RateLimitError(
            message=f"Please wait {cooldown:.0f}s before performing this action again.",
            code="llm.cooldown",
            retry_after_seconds=int(cooldown - (now - last_time)) + 1,
        )
    user_actions[action] = now

    # 4. Hosted credit check
    if user.hosted_credits_used >= user.hosted_credits_limit:
        raise ValidationError(
            message="Monthly AI credits exhausted. Upgrade your plan for more.",
            code="llm.credits_exhausted",
            hint="Visit Settings > Billing to upgrade your plan.",
        )

    # 5. Debate access check (if debate_id provided)
    if debate_id:
        debate = session.get(Debate, debate_id)
        if not debate:
            from routes.common import can_access_debate
            raise PermissionError(
                message="Debate not found",
                code="llm.debate_not_found",
            )
        from routes.common import can_access_debate
        if not can_access_debate(debate, user, session):
            raise PermissionError(
                message="You do not have access to this debate",
                code="llm.permission_denied",
            )

    # 6. Consume credit
    user.hosted_credits_used += estimated_cost_units
    session.add(user)
    session.commit()
