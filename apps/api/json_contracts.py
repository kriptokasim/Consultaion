"""JSON contract versioning for evolvable database JSON columns.

Provides typed schemas, validation, and migration support for critical
JSON blobs like ``Debate.config`` and ``Debate.final_meta``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DebateConfigVersion(int, Enum):
    V1 = 1
    V2 = 2
    CURRENT = V2


class AgentConfig(BaseModel):
    model: str = "default"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class JudgeConfig(BaseModel):
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
    data["schema_version"] = 2
    if "agents" not in data:
        data["agents"] = []
    if "judges" not in data:
        data["judges"] = []
    if "max_rounds" not in data:
        data["max_rounds"] = 5
    if "mode" not in data:
        data["mode"] = "parliament"
    return data


def migrate_final_meta_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = 2
    data.setdefault("attempt_count", 0)
    data.setdefault("continuation_count", 0)
    data.setdefault("provider_calls", 0)
    data.setdefault("total_tokens", 0)
    return data


def validate_debate_config(data: dict[str, Any]) -> DebateConfigV2:
    version = data.get("schema_version", 1)
    if version == 1:
        data = migrate_config_v1_to_v2(data)
    return DebateConfigV2.model_validate(data)


def validate_final_meta(data: dict[str, Any]) -> FinalMetaV2:
    version = data.get("schema_version", 1)
    if version == 1:
        data = migrate_final_meta_v1_to_v2(data)
    return FinalMetaV2.model_validate(data)


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
