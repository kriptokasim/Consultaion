from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

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
    id: str = Field(..., description="Unique event identifier (ULID or UUID).")
    debate_id: str
    ts: datetime
    type: str = Field(..., description="Event type (message, score, vote, notice, etc).")
    round: int = Field(default=0, description="Round index.")
    seat: Optional[str] = Field(default=None, description="Seat ID or name if applicable.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event-specific data.")
