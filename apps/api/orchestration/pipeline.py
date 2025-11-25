import logging
from typing import List

from .interfaces import DebateContext, DebatePipeline, DebateStage, DebateState
from .stages import DraftStage, CritiqueStage, JudgeStage, SynthesisStage
from .state import DebateStateManager

logger = logging.getLogger(__name__)


class StandardDebatePipeline(DebatePipeline):
    """
    The standard debate flow: Draft -> Critique -> Judge -> Synthesis.
    """
    def __init__(self, state_manager: DebateStateManager):
        self.stages: List[DebateStage] = [
            DraftStage(state_manager),
            CritiqueStage(state_manager),
            JudgeStage(state_manager),
            SynthesisStage(state_manager),
        ]

    async def execute(self, context: DebateContext) -> DebateState:
        state = DebateState()
        
        for stage in self.stages:
            logger.info("Debate %s: starting stage %s", context.debate_id, stage.name)
            try:
                state = await stage.run(context, state)
            except Exception as exc:
                logger.error("Debate %s: stage %s failed: %s", context.debate_id, stage.name, exc)
                raise
                
        state.status = "completed"
        return state
