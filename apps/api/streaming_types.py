"""Canonical streaming event types for the Consultaion real-time protocol.

Defines the envelope structure and all event type payloads used in SSE
communication between backend and frontend during a run.

Usage:
    from streaming_types import StreamEvent, StreamEventType
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StreamEventType(str, Enum):
    """All canonical streaming event types."""
    # Run lifecycle
    RUN_ACCEPTED = "run_accepted"
    RUN_WORKER_STARTED = "run_worker_started"

    # Model response lifecycle
    MODEL_RESPONSE_QUEUED = "model_response_queued"
    MODEL_RESPONSE_CONNECTING = "model_response_connecting"
    MODEL_RESPONSE_STARTED = "model_response_started"
    MODEL_RESPONSE_DELTA = "model_response_delta"
    MODEL_RESPONSE_PERSISTING = "model_response_persisting"
    MODEL_RESPONSE_COMPLETED = "model_response_completed"
    MODEL_RESPONSE_FAILED = "model_response_failed"

    # Pipeline stages
    PERSPECTIVES_READY = "perspectives_ready"
    SYNTHESIS_STARTED = "synthesis_started"
    SYNTHESIS_COMPLETED = "synthesis_completed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"

    # Terminal
    DEBATE_COMPLETED = "debate_completed"
    DEBATE_FAILED = "debate_failed"


@dataclass
class StreamEnvelope:
    """Common envelope for all streaming events."""
    event_id: str
    type: StreamEventType
    debate_id: str
    run_attempt_id: str | None = None
    response_id: str | None = None
    sequence: int = 0
    created_at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.event_id,
            "type": self.type.value,
            "debate_id": self.debate_id,
            "run_attempt_id": self.run_attempt_id,
            "response_id": self.response_id,
            "sequence": self.sequence,
            "timestamp": self.created_at,
            "payload": self.payload,
        }


@dataclass
class ModelResponseDelta:
    """Payload for MODEL_RESPONSE_DELTA events."""
    response_id: str
    model_id: str
    text: str
    sequence: int
    accumulated_chars: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "response_id": self.response_id,
            "model_id": self.model_id,
            "text": self.text,
            "delta_sequence": self.sequence,
            "accumulated_chars": self.accumulated_chars,
        }


def build_envelope(
    *,
    event_type: StreamEventType,
    debate_id: str,
    sequence: int,
    run_attempt_id: str | None = None,
    response_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a streaming event envelope dict for SSE publish."""
    import time
    import uuid

    envelope = StreamEnvelope(
        event_id=f"evt-{uuid.uuid4().hex[:12]}",
        type=event_type,
        debate_id=debate_id,
        run_attempt_id=run_attempt_id,
        response_id=response_id,
        sequence=sequence,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        payload=payload or {},
    )
    return envelope.to_dict()
