"""JSON contract versioning for evolvable database JSON columns.

Provides typed schemas, validation, and migration support for critical
JSON blobs like ``Debate.config`` and ``Debate.final_meta``.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DebateConfigVersion(int, Enum):
    V1 = 1
    V2 = 2
    CURRENT = V2


class AgentConfig(BaseModel):
    # Production DebateConfig has evolved beyond this legacy contract shape.
    # Preserve unknown nested fields (name/persona/tools, etc.) so validation
    # can never become a lossy transformation if a caller serializes the result.
    model_config = {"extra": "allow"}
    model: str = "default"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class JudgeConfig(BaseModel):
    # Preserve production fields such as name/rubrics while retaining backwards
    # compatibility with the original versioned contract.
    model_config = {"extra": "allow"}
    model: str = "default"
    system_prompt: str = ""
    criteria: list[str] = Field(default_factory=list)


class DebateConfigV2(BaseModel):
    model_config = {"extra": "allow"}
    schema_version: Literal[2] = 2
    agents: list[AgentConfig] = Field(default_factory=list)
    judges: list[JudgeConfig] = Field(default_factory=list)
    max_rounds: int = 5
    budget_limit: Optional[float] = None
    mode: str = "parliament"
    language: str = "en"


class FinalMetaV1(BaseModel):
    model_config = {"extra": "allow"}
    schema_version: Literal[1] = 1
    winner: Optional[str] = None
    scores: dict[str, float] = Field(default_factory=dict)
    summary: Optional[str] = None
    duration_ms: Optional[int] = None


class FinalMetaV2(BaseModel):
    model_config = {"extra": "allow"}
    schema_version: Literal[2] = 2
    winner: Optional[str] = None
    scores: dict[str, float] = Field(default_factory=dict)
    summary: Optional[str] = None
    duration_ms: Optional[int] = None
    attempt_count: int = 0
    continuation_count: int = 0
    provider_calls: int = 0
    total_tokens: int = 0


def migrate_config_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    # Never mutate an ORM-owned JSON dict on a read/validation path. A caller may
    # pass Debate.config directly; in-place migration can otherwise leak state
    # into later serialization or an unrelated transaction.
    migrated = deepcopy(data)
    migrated["schema_version"] = 2
    if "agents" not in migrated:
        migrated["agents"] = []
    if "judges" not in migrated:
        migrated["judges"] = []
    if "max_rounds" not in migrated:
        migrated["max_rounds"] = 5
    if "mode" not in migrated:
        migrated["mode"] = "parliament"
    return migrated


def migrate_final_meta_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(data)
    migrated["schema_version"] = 2
    migrated.setdefault("attempt_count", 0)
    migrated.setdefault("continuation_count", 0)
    migrated.setdefault("provider_calls", 0)
    migrated.setdefault("total_tokens", 0)
    return migrated


def validate_debate_config(data: dict[str, Any]) -> DebateConfigV2:
    version = data.get("schema_version", 1)
    candidate = migrate_config_v1_to_v2(data) if version == 1 else deepcopy(data)
    return DebateConfigV2.model_validate(candidate)


def validate_final_meta(data: dict[str, Any]) -> FinalMetaV2:
    version = data.get("schema_version", 1)
    candidate = migrate_final_meta_v1_to_v2(data) if version == 1 else deepcopy(data)
    return FinalMetaV2.model_validate(candidate)


def safe_validate_config(data: dict[str, Any] | None) -> DebateConfigV2 | None:
    if data is None:
        return None
    try:
        return validate_debate_config(data)
    except Exception:
        return None


def safe_validate_final_meta(data: dict[str, Any] | None) -> FinalMetaV2 | None:
    if data is None:
        return None
    try:
        return validate_final_meta(data)
    except Exception:
        return None
