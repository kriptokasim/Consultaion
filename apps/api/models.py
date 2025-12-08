from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime, Index, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False)
    password_hash: str = Field(nullable=False)
    role: str = Field(default="user", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    is_active: bool = Field(default=True, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    display_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None, sa_column=Column(Text))
    timezone: Optional[str] = Field(default=None)
    email_summaries_enabled: bool = Field(default=False, nullable=False)
    
    # Patchset 55.0: Subscription plan for quota enforcement
    plan: str = Field(default="free", max_length=50, nullable=False, index=True)


class SupportNote(SQLModel, table=True):
    """Admin support notes for tracking user interactions."""
    __tablename__ = "support_note"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    author_id: Optional[str] = Field(foreign_key="user.id", default=None, index=True)
    note: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class APIKey(SQLModel, table=True):
    """
    API Key model for programmatic access.
    
    Patchset 37.0: Enhanced with prefix, revoked, and team support.
    """
    __tablename__ = "api_keys"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    team_id: Optional[str] = Field(default=None, foreign_key="team.id", index=True)
    name: str = Field(nullable=False)  # User-defined label
    prefix: str = Field(nullable=False, index=True)  # Short public prefix (e.g., "pk_abc123")
    hashed_key: str = Field(nullable=False)  # Full key hashed with bcrypt
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    last_used_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    revoked: bool = Field(default=False, nullable=False, index=True)



class Debate(SQLModel, table=True):
    model_config = SQLModel.model_config.copy()
    model_config["protected_namespaces"] = ()
    id: str = Field(primary_key=True)
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="queued", nullable=False, index=True)
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    panel_config: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    engine_version: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    model_id: Optional[str] = Field(default=None, index=True, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    final_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    final_meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    user_id: Optional[str] = Field(foreign_key="user.id", default=None, index=True, nullable=True)
    team_id: Optional[str] = Field(foreign_key="team.id", default=None, index=True, nullable=True)
    routed_model: Optional[str] = Field(default=None, index=True, nullable=True)
    routing_policy: Optional[str] = Field(default=None, nullable=True)
    routing_meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    mode: str = Field(default="debate", nullable=False, index=True)


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


class Team(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, nullable=False)
    name: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class TeamMember(SQLModel, table=True):
    __tablename__ = "team_member"
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: str = Field(foreign_key="team.id", nullable=False, index=True)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    role: str = Field(default="viewer", nullable=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class UsageQuota(SQLModel, table=True):
    __tablename__ = "usage_quota"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    period: str = Field(nullable=False, index=True)
    max_runs: Optional[int] = Field(default=None)
    max_tokens: Optional[int] = Field(default=None)
    reset_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class UsageCounter(SQLModel, table=True):
    __tablename__ = "usage_counter"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    period: str = Field(nullable=False, index=True)
    runs_used: int = Field(default=0, nullable=False)
    tokens_used: int = Field(default=0, nullable=False)
    window_start: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(foreign_key="user.id", default=None, index=True, nullable=True)
    action: str = Field(nullable=False)
    target_type: Optional[str] = Field(default=None)
    target_id: Optional[str] = Field(default=None, index=True)
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class PairwiseVote(SQLModel, table=True):
    __tablename__ = "pairwise_vote"
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: str = Field(foreign_key="debate.id", nullable=False, index=True)
    category: Optional[str] = Field(default=None, index=True)
    candidate_a: str = Field(nullable=False)
    candidate_b: str = Field(nullable=False)
    winner: str = Field(nullable=False, index=True)
    judge_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[str] = Field(foreign_key="user.id", default=None, index=True, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class RatingPersona(SQLModel, table=True):
    __tablename__ = "rating_persona"
    id: Optional[int] = Field(default=None, primary_key=True)
    persona: str = Field(nullable=False, index=True)
    category: Optional[str] = Field(default=None, index=True)
    elo: float = Field(default=1500.0, nullable=False)
    stdev: float = Field(default=0.0, nullable=False)
    n_matches: int = Field(default=0, nullable=False)
    win_rate: float = Field(default=0.0, nullable=False)
    ci_low: float = Field(default=0.0, nullable=False)
    ci_high: float = Field(default=0.0, nullable=False)
    last_updated: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AdminEvent(SQLModel, table=True):
    __tablename__ = "admin_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    level: str = Field(index=True)  # error, warning, info
    message: str = Field(sa_column=Column(Text, nullable=False))
    trace_id: Optional[str] = Field(default=None, index=True)
    debate_id: Optional[str] = Field(default=None, index=True)
    meta: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
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
Index("ix_usage_counter_user_period", UsageCounter.user_id, UsageCounter.period, unique=True)
Index("ix_usage_quota_user_period", UsageQuota.user_id, UsageQuota.period, unique=True)
Index("ix_audit_log_created_at", AuditLog.created_at)
Index("ix_pairwise_vote_candidates", PairwiseVote.candidate_a, PairwiseVote.candidate_b)
Index("ix_rating_persona_unique", RatingPersona.persona, RatingPersona.category, unique=True)
Index("ix_admin_event_created_at", AdminEvent.created_at)
