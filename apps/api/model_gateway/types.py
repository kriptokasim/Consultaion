from pydantic import BaseModel, ConfigDict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, AsyncIterator, Callable, Awaitable

class GatewayRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    messages: List[Dict[str, str]]
    model_id: str
    role: str
    temperature: float = 0.3
    max_tokens: int = 600
    gateway_policy: str = "auto"
    user_id: Optional[str] = None
    user_plan: Optional[str] = "free"
    debate_id: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Dict[str, Any]] = None

class GatewayDecision(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    selected_model: str
    selected_provider: str
    policy_used: str
    model_pool: str
    estimated_cost_usd: float
    fallback_enabled: bool

class GatewayModelCallResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    content: str
    model_used: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    gateway: str = "model_gateway_v1"
    model_pool: str
    routing_policy: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    retry_count: int = 0
    user_plan: Optional[str] = None
    error_code: Optional[str] = None
    ttft_ms: Optional[float] = None


@dataclass
class ModelDelta:
    """A single streaming delta from an LLM provider."""
    text: str
    sequence: int
    accumulated_chars: int


# Callback type for streaming deltas
OnDeltaCallback = Callable[[ModelDelta], Awaitable[None]]


class GatewayError(Exception):
    """Base exception for gateway errors."""
    pass

class GatewayQuotaExceededError(GatewayError):
    """Raised when user exceeds gateway quota/cost caps."""
    pass

class GatewayModelRestrictedError(GatewayError):
    """Raised when the requested model is restricted for the user's plan."""
    pass
