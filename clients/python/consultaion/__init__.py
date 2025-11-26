"""Official Python SDK for Consultaion API."""

from .client import ConsultaionClient
from .types import (
    Debate,
    DebateConfig,
    DebateCreateOptions,
    DebateEvent,
    RoutingCandidate,
    RoutingMeta,
)

__version__ = "0.1.0"

__all__ = [
    "ConsultaionClient",
    "Debate",
    "DebateConfig",
    "DebateCreateOptions",
    "DebateEvent",
    "RoutingCandidate",
    "RoutingMeta",
]
