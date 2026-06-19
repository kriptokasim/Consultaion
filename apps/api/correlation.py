"""End-to-end correlation context for tracing user actions through the stack."""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

_corr_ctx: contextvars.ContextVar["CorrelationContext"] = contextvars.ContextVar(
    "correlation_context"
)


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Typed correlation context for request tracing."""

    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:16]}")
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:24]}")
    user_id: Optional[str] = None
    debate_id: Optional[str] = None
    attempt_id: Optional[str] = None
    continuation_id: Optional[str] = None
    task_id: Optional[str] = None
    provider_call_id: Optional[str] = None

    def with_debate(self, debate_id: str) -> "CorrelationContext":
        return CorrelationContext(**{**asdict(self), "debate_id": debate_id})

    def with_attempt(self, attempt_id: str) -> "CorrelationContext":
        return CorrelationContext(**{**asdict(self), "attempt_id": attempt_id})

    def with_continuation(self, continuation_id: str) -> "CorrelationContext":
        return CorrelationContext(**{**asdict(self), "continuation_id": continuation_id})

    def with_task(self, task_id: str) -> "CorrelationContext":
        return CorrelationContext(**{**asdict(self), "task_id": task_id})

    def with_provider_call(self, provider_call_id: str) -> "CorrelationContext":
        return CorrelationContext(**{**asdict(self), "provider_call_id": provider_call_id})

    def to_log_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
        }
        if self.user_id:
            fields["user_id"] = self.user_id
        if self.debate_id:
            fields["debate_id"] = self.debate_id
        if self.attempt_id:
            fields["attempt_id"] = self.attempt_id
        if self.continuation_id:
            fields["continuation_id"] = self.continuation_id
        if self.task_id:
            fields["task_id"] = self.task_id
        if self.provider_call_id:
            fields["provider_call_id"] = self.provider_call_id
        return fields

    def to_headers(self) -> dict[str, str]:
        return {
            "X-Request-ID": self.request_id,
            "X-Trace-ID": self.trace_id,
        }

    def to_sse_metadata(self) -> dict[str, str]:
        safe_fields: dict[str, str] = {}
        if self.trace_id:
            safe_fields["trace_id"] = self.trace_id
        if self.debate_id:
            safe_fields["debate_id"] = self.debate_id
        if self.attempt_id:
            safe_fields["attempt_id"] = self.attempt_id
        return safe_fields


def get_correlation_context() -> Optional[CorrelationContext]:
    return _corr_ctx.get(None)


def set_correlation_context(ctx: CorrelationContext) -> contextvars.Token:
    return _corr_ctx.set(ctx)


def current_correlation() -> CorrelationContext:
    ctx = get_correlation_context()
    if ctx is None:
        ctx = CorrelationContext()
        set_correlation_context(ctx)
    return ctx


def ensure_correlation(user_id: Optional[str] = None) -> CorrelationContext:
    ctx = get_correlation_context()
    if ctx is None:
        ctx = CorrelationContext(user_id=user_id)
        set_correlation_context(ctx)
    return ctx


def create_child_context(
    *,
    user_id: Optional[str] = None,
    debate_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    continuation_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> CorrelationContext:
    parent = get_correlation_context()
    if parent is None:
        parent = CorrelationContext()

    merged = asdict(parent)
    if user_id:
        merged["user_id"] = user_id
    if debate_id:
        merged["debate_id"] = debate_id
    if attempt_id:
        merged["attempt_id"] = attempt_id
    if continuation_id:
        merged["continuation_id"] = continuation_id
    if task_id:
        merged["task_id"] = task_id

    child = CorrelationContext(**merged)
    set_correlation_context(child)
    return child
