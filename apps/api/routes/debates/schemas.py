from typing import Optional

from pydantic import BaseModel


class DebateUpdate(BaseModel):
    team_id: Optional[str] = None


class DebateShare(BaseModel):
    is_public: bool


class DebateModerateRequest(BaseModel):
    round_index: int
    moderation_steering: str


class DebateListResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int
    has_more: bool


class RetryRequest(BaseModel):
    stage_key: Optional[str] = None


class RetryAgentRequest(BaseModel):
    persona: str


class ContinuationResolveRequest(BaseModel):
    idempotency_key: str
