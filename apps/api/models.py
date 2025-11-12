from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Index, JSON, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Debate(SQLModel, table=True):
    id: str = Field(primary_key=True)
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="queued", nullable=False, index=True)
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    final_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    final_meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class DebateRound(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    index: int
    label: str
    note: Optional[str] = None
    started_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    ended_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    round_index: int = Field(index=True)
    role: str
    persona: Optional[str] = None
    content: str = Field(sa_column=Column(Text, nullable=False))
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class Score(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    persona: str = Field(index=True)
    judge: str = Field(index=True)
    score: float = Field(index=True)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class Vote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    method: str
    rankings: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    weights: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    result: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


Index("ix_message_debate_round", Message.debate_id, Message.round_index)
Index("ix_score_debate_persona", Score.debate_id, Score.persona)
Index("ix_round_debate_index", DebateRound.debate_id, DebateRound.index)
Index("ix_debate_created_at", Debate.created_at)
Index("ix_debate_updated_at", Debate.updated_at)
Index("ix_debateround_started_at", DebateRound.started_at)
Index("ix_debateround_ended_at", DebateRound.ended_at)
Index("ix_message_created_at", Message.created_at)
Index("ix_score_created_at", Score.created_at)
Index("ix_vote_created_at", Vote.created_at)
