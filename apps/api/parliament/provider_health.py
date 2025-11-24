"""
Provider health tracking and circuit breaker implementation.

Tracks error rates for LLM providers and implements circuit breaker pattern
to prevent cascading failures when providers are unhealthy.

Patchset 28.0
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple

from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)


class ProviderHealthState(BaseModel):
    """Tracks health metrics for a specific provider/model combination."""
    
    provider: str
    model: str
    window_seconds: int
    error_threshold: float
    min_calls: int
    cooldown_seconds: int
    
    total_calls: int = 0
    error_calls: int = 0
    last_opened: datetime | None = None
    last_checked: datetime | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def should_open(self, now: datetime) -> bool:
        """
        Determine if circuit breaker should open based on error rate.
        
        Args:
            now: Current timestamp
            
        Returns:
            True if circuit should open due to high error rate
        """
        if self.total_calls < self.min_calls:
            return False
        
        error_rate = self.error_calls / self.total_calls if self.total_calls > 0 else 0
        return error_rate >= self.error_threshold
    
    def is_open(self, now: datetime) -> bool:
        """
        Check if circuit breaker is currently open (blocking calls).
        
        Args:
            now: Current timestamp
            
        Returns:
            True if circuit is open and still in cooldown period
        """
        if self.last_opened is None:
            return False
        
        elapsed = (now - self.last_opened).total_seconds()
        return elapsed < self.cooldown_seconds
    
    def record_success(self, now: datetime) -> None:
        """Record a successful LLM call."""
        self.total_calls += 1
        self.last_checked = now
        
        logger.debug(
            f"Provider health: {self.provider}/{self.model} success "
            f"(calls={self.total_calls}, errors={self.error_calls})"
        )
    
    def record_error(self, now: datetime) -> None:
        """
        Record a failed LLM call and potentially open circuit.
        
        Args:
            now: Current timestamp
        """
        self.total_calls += 1
        self.error_calls += 1
        self.last_checked = now
        
        logger.warning(
            f"Provider health: {self.provider}/{self.model} error "
            f"(calls={self.total_calls}, errors={self.error_calls}, "
            f"error_rate={self.error_calls/self.total_calls:.2%})"
        )
        
        if self.should_open(now) and not self.is_open(now):
            self.last_opened = now
            logger.error(
                f"Circuit breaker OPENED for {self.provider}/{self.model} "
                f"(error_rate={self.error_calls/self.total_calls:.2%} "
                f"threshold={self.error_threshold:.2%})"
            )


# Global registry of health states
# Key: (provider, model) -> ProviderHealthState
_health_registry: Dict[Tuple[str, str], ProviderHealthState] = {}


def get_health_state(provider: str, model: str) -> ProviderHealthState:
    """
    Get or create health state for a provider/model combination.
    
    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")
        
    Returns:
        ProviderHealthState for tracking this provider/model
    """
    key = (provider, model)
    
    if key not in _health_registry:
        _health_registry[key] = ProviderHealthState(
            provider=provider,
            model=model,
            window_seconds=settings.PROVIDER_HEALTH_WINDOW_SECONDS,
            error_threshold=settings.PROVIDER_HEALTH_ERROR_THRESHOLD,
            min_calls=settings.PROVIDER_HEALTH_MIN_CALLS,
            cooldown_seconds=settings.PROVIDER_HEALTH_COOLDOWN_SECONDS,
        )
        logger.info(f"Created health state for {provider}/{model}")
    
    return _health_registry[key]


def record_call_result(provider: str, model: str, success: bool, now: datetime | None = None) -> None:
    """
    Record the result of an LLM call for health tracking.
    
    Args:
        provider: Provider name
        model: Model identifier
        success: True if call succeeded, False if it failed
        now: Current timestamp (defaults to now if not provided)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    health_state = get_health_state(provider, model)
    
    if success:
        health_state.record_success(now)
    else:
        health_state.record_error(now)


def get_all_health_states() -> list[ProviderHealthState]:
    """
    Get all tracked provider health states.
    
    Returns:
        List of all ProviderHealthState objects in the registry
    """
    return list(_health_registry.values())


def reset_health_state(provider: str, model: str) -> None:
    """
    Reset health state for a provider/model (useful for testing).
    
    Args:
        provider: Provider name
        model: Model identifier
    """
    key = (provider, model)
    if key in _health_registry:
        del _health_registry[key]
        logger.info(f"Reset health state for {provider}/{model}")


def clear_all_health_states() -> None:
    """Clear all health states (useful for testing)."""
    _health_registry.clear()
    logger.info("Cleared all provider health states")
