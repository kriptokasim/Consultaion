"""SLO definitions and budget-burn tracking.

Defines Service Level Objectives for Consultaion and provides
in-process budget-burn rate tracking using sliding windows.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SLODefinition:
    name: str
    target: float  # e.g. 0.999 = 99.9%
    window_seconds: int  # e.g. 28 days
    description: str = ""


@dataclass
class SLOStatus:
    name: str
    target: float
    current_success_rate: float
    error_budget_remaining_seconds: float
    window_seconds: int
    total_requests: int
    failed_requests: int
    burning: bool


# ── Consultaion SLOs ──────────────────────────────────────────────────────

SLO_REGISTRY: Dict[str, SLODefinition] = {
    "api_availability": SLODefinition(
        name="api_availability",
        target=0.999,  # 99.9% availability
        window_seconds=28 * 86400,  # 28 days
        description="Non-error HTTP responses (exclude 4xx) / total requests",
    ),
    "llm_inference_latency": SLODefinition(
        name="llm_inference_latency",
        target=0.95,  # 95% under threshold
        window_seconds=7 * 86400,  # 7 days
        description="LLM inference requests completing under 30 seconds",
    ),
    "debate_success_rate": SLODefinition(
        name="debate_success_rate",
        target=0.98,  # 98% success
        window_seconds=7 * 86400,
        description="Debates reaching terminal state (completed/degraded) without internal failure",
    ),
    "sse_delivery": SLODefinition(
        name="sse_delivery",
        target=0.99,  # 99% delivery
        window_seconds=7 * 86400,
        description="SSE messages delivered to connected clients within 5 seconds",
    ),
}


class SLOBudgetTracker:
    """In-process sliding-window budget burn tracker.

    For production, replace with Prometheus-backed queries.
    """

    def __init__(self, window_seconds: int = 86400):
        self._window = window_seconds
        self._events: List[tuple[float, bool]] = []  # (timestamp, success)
        self._max_events = 100000

    def record(self, success: bool) -> None:
        now = time.time()
        self._events.append((now, success))
        # Evict old events
        cutoff = now - self._window
        self._events = [e for e in self._events if e[0] >= cutoff]
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def success_rate(self) -> float:
        if not self._events:
            return 1.0
        return sum(1 for _, s in self._events if s) / len(self._events)

    def error_budget_remaining(self, target: float) -> float:
        if not self._events:
            return self._window * target
        total = len(self._events)
        errors = sum(1 for _, s in self._events if not s)
        allowed_errors = total * (1 - target)
        remaining = max(0, allowed_errors - errors)
        if total == 0:
            return self._window * target
        return (remaining / total) * self._window

    def is_burning(self, target: float, threshold: float = 2.0) -> bool:
        """Check if error budget is burning faster than allowed."""
        if not self._events:
            return False
        recent = self._events[-min(100, len(self._events)):]
        if not recent:
            return False
        recent_error_rate = sum(1 for _, s in recent if not s) / len(recent)
        allowed_error_rate = 1 - target
        return recent_error_rate > allowed_error_rate * threshold


# Global tracker instances
_trackers: Dict[str, SLOBudgetTracker] = {}


def get_slo_tracker(slo_name: str) -> SLOBudgetTracker:
    if slo_name not in _trackers:
        defn = SLO_REGISTRY.get(slo_name)
        window = defn.window_seconds if defn else 86400
        _trackers[slo_name] = SLOBudgetTracker(window_seconds=min(window, 86400))
    return _trackers[slo_name]


def record_slo_event(slo_name: str, success: bool) -> None:
    tracker = get_slo_tracker(slo_name)
    tracker.record(success)


def get_slo_status(slo_name: str) -> Optional[SLOStatus]:
    defn = SLO_REGISTRY.get(slo_name)
    if not defn:
        return None
    tracker = get_slo_tracker(slo_name)
    rate = tracker.success_rate()
    budget = tracker.error_budget_remaining(defn.target)
    burning = tracker.is_burning(defn.target)
    total = len(tracker._events)
    failed = sum(1 for _, s in tracker._events if not s)
    return SLOStatus(
        name=defn.name,
        target=defn.target,
        current_success_rate=rate,
        error_budget_remaining_seconds=budget,
        window_seconds=defn.window_seconds,
        total_requests=total,
        failed_requests=failed,
        burning=burning,
    )


def get_all_slo_statuses() -> Dict[str, SLOStatus]:
    result = {}
    for name in SLO_REGISTRY:
        status = get_slo_status(name)
        if status:
            result[name] = status
    return result
