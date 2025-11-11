from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Index, JSON, Text
from sqlmodel import Field, SQLModel


class Debate(SQLModel, table=True):
    id: str = Field(primary_key=True)
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="queued", nullable=False, index=True)
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    final_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    final_meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class DebateRound(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    index: int
    label: str
    note: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    ended_at: Optional[datetime] = Field(default=None, index=True)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    round_index: int = Field(index=True)
    role: str
    persona: Optional[str] = None
    content: str = Field(sa_column=Column(Text, nullable=False))
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class Score(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    persona: str = Field(index=True)
    judge: str = Field(index=True)
    score: float = Field(index=True)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


Index("ix_message_debate_round", Message.debate_id, Message.round_index)
Index("ix_score_debate_persona", Score.debate_id, Score.persona)
Index("ix_round_debate_index", DebateRound.debate_id, DebateRound.index)


class Vote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    method: str
    rankings: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    weights: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    result: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
