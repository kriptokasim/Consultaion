from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents import UsageAccumulator


@dataclass
class DebateContext:
    """
    Context object passed through the pipeline.
    Holds configuration, runtime flags, and shared resources.
    """
    debate_id: str
    prompt: str
    config: Dict[str, Any]
    channel_id: str
    model_id: Optional[str] = None
    # Shared resources
    usage_tracker: UsageAccumulator = field(default_factory=UsageAccumulator)
    
    # Runtime flags
    is_mock: bool = False


@dataclass
class DebateState:
    """
    Mutable state of the debate execution.
    Holds intermediate results, scores, and status.
    """
    status: str = "running"
    round_index: int = 0
    
    # Data accumulated across stages
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    revised_candidates: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[Dict[str, Any]] = field(default_factory=list)
    ranking: List[str] = field(default_factory=list)
    vote_details: Dict[str, Any] = field(default_factory=dict)
    final_content: Optional[str] = None
    final_meta: Dict[str, Any] = field(default_factory=dict)
    
    # Error tracking
    error: Optional[str] = None
    failed_seats: List[str] = field(default_factory=list)


class DebateStage(ABC):
    """
    Interface for a single stage in the debate pipeline.
    """
    name: str

    @abstractmethod
    async def run(self, context: DebateContext, state: DebateState) -> DebateState:
        """
        Execute the stage logic.
        Modifies and returns the state.
        """
        pass


class DebatePipeline(ABC):
    """
    Interface for a sequence of stages.
    """
    @abstractmethod
    async def execute(self, context: DebateContext) -> DebateState:
        """
        Run the full pipeline.
        """
        pass
