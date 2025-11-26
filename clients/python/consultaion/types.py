"""Type definitions for Consultaion API."""

from typing import Any, Dict, List, Literal, NotRequired, TypedDict


class AgentConfig(TypedDict):
    """Configuration for a debate agent."""

    name: str
    persona: str
    model: NotRequired[str]
    tools: NotRequired[List[str]]


class JudgeConfig(TypedDict):
    """Configuration for a debate judge."""

    name: str
    model: NotRequired[str]
    rubrics: NotRequired[List[str]]


class DebateConfig(TypedDict):
    """Configuration for a debate."""

    agents: NotRequired[List[AgentConfig]]
    judges: NotRequired[List[JudgeConfig]]


class DebateCreateOptions(TypedDict):
    """Options for creating a new debate."""

    prompt: str
    """The question or topic for the debate."""

    model_id: NotRequired[str]
    """Optional explicit model ID to use."""

    routing_policy: NotRequired[Literal["router-smart", "router-deep"]]
    """Optional routing policy for model selection."""

    config: NotRequired[DebateConfig]
    """Optional debate configuration."""


class RoutingCandidate(TypedDict):
    """Routing candidate information."""

    model: str
    total_score: float
    cost_score: float
    latency_score: float
    quality_score: float
    safety_score: float
    is_healthy: bool


class RoutingMeta(TypedDict):
    """Routing metadata."""

    candidates: NotRequired[List[RoutingCandidate]]
    requested_model: NotRequired[str]


class Debate(TypedDict):
    """Debate object."""

    id: str
    prompt: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    updated_at: NotRequired[str]
    user_id: str
    model_id: NotRequired[str]
    routed_model: NotRequired[str]
    routing_policy: NotRequired[str]
    routing_meta: NotRequired[RoutingMeta]
    config: NotRequired[Dict[str, Any]]
    error: NotRequired[str]


class DebateEvent(TypedDict):
    """Server-sent event from a debate."""

    type: str
    data: Dict[str, Any]
    timestamp: NotRequired[str]
