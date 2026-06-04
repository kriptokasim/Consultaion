from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Optional, Any

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

class GatewayError(Exception):
    """Base exception for gateway errors."""
    pass

class GatewayQuotaExceededError(GatewayError):
    """Raised when user exceeds gateway quota/cost caps."""
    pass

class GatewayModelRestrictedError(GatewayError):
    """Raised when the requested model is restricted for the user's plan."""
    pass
