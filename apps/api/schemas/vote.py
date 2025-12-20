"""
Patchset 76: Vote schema extensions for enhanced voting UX.

Adds optional metadata fields for structured vote reasons and confidence levels.
All fields are optional for backward compatibility.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VoteReason(BaseModel):
    """Structured reason for a vote selection."""
    reason: Optional[Literal["clarity", "correctness", "completeness", "creativity"]] = Field(
        None,
        description="Optional structured reason for the vote"
    )
    confidence: Optional[int] = Field(
        None,
        ge=1,
        le=3,
        description="Vote confidence level: 1=unsure, 2=confident, 3=very confident"
    )


class VoteCreate(BaseModel):
    """Request schema for submitting a vote with optional metadata."""
    debate_id: str = Field(..., description="ID of the debate being voted on")
    choice: str = Field(..., description="The vote choice (e.g., persona ID, 'up', 'down')")
    reason: Optional[Literal["clarity", "correctness", "completeness", "creativity"]] = Field(
        None,
        description="Optional structured reason for the vote"
    )
    confidence: Optional[int] = Field(
        None,
        ge=1,
        le=3,
        description="Vote confidence level: 1=unsure, 2=confident, 3=very confident"
    )


class VoteResponse(BaseModel):
    """Response after submitting a vote."""
    success: bool = True
    vote_id: Optional[int] = None
    message: str = "Vote recorded"
