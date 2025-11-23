from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any
from typing import Literal

from pydantic import BaseModel, Field


class SeatLLMEnvelope(BaseModel):
    content: str
    reasoning: Optional[str] = None
    stance: Optional[str] = None


class SeatMessage(BaseModel):
    seat_id: str = Field(..., description="Internal seat identifier (e.g. 'seat-1').")
    role_id: str = Field(..., description="Logical role id (e.g. 'devils_advocate').")
    provider: str = Field(..., description="LLM provider key (e.g. 'openai').")
    model: str = Field(..., description="Concrete model name (e.g. 'gpt-4o').")

    content: str = Field(..., description="Natural language message produced by this seat.")
    reasoning: Optional[str] = Field(
        None,
        description="Optional chain-of-thought or explanation; used internally, not exposed raw.",
    )
    stance: Optional[str] = Field(
        None,
        description="Short label summarizing the seat's stance (e.g. 'support', 'oppose', or 'neutral').",
    )

    round_index: int = Field(..., description="Zero-based round index for this message.")
    created_at: datetime = Field(..., description="UTC timestamp when the seat message was recorded.")


class RoundSummary(BaseModel):
    round_index: int
    winning_seat_id: Optional[str] = None
    rationale: Optional[str] = None


class DebateSnapshot(BaseModel):
    debate_id: str
    round_index: int
    seat_messages: List[SeatMessage]
    summary: Optional[RoundSummary] = None


class TimelineEvent(BaseModel):
    ts: datetime
    debate_id: str
    round_index: int
    phase: str
    seat_id: str
    seat_role: str
    provider: Optional[str] = None
    model: Optional[str] = None
    event_type: Literal["seat_message", "system_notice", "score_update", "summary"]
    content: Optional[str] = None
    stance: Optional[str] = None
    reasoning: Optional[str] = None
    score: Optional[float] = None
    meta: Optional[dict[str, Any]] = None
