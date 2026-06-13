import logging
from typing import List

from .interfaces import DebateContext, DebatePipeline, DebateStage, DebateState
from .stages import CritiqueStage, DraftStage, JudgeStage, SynthesisStage
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
        from config import settings
        state = DebateState()
        
        if context.is_resume:
            from database_async import async_session_scope
            from models import Message
            from sqlmodel import select

            async with async_session_scope() as session:
                stmt = select(Message).where(Message.debate_id == context.debate_id)
                result = await session.execute(stmt)
                messages = result.scalars().all()

            candidates = []
            revised = []
            for msg in messages:
                if msg.role == "candidate":
                    candidates.append({
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    })
                elif msg.role == "revised":
                    revised.append({
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    })
            state.candidates = candidates
            state.revised_candidates = revised
            logger.info("Resuming debate %s: loaded %d candidates and %d revised candidates", context.debate_id, len(candidates), len(revised))
        
        for stage in self.stages:
            logger.info("Debate %s: starting stage %s", context.debate_id, stage.name)
            try:
                state = await stage.run(context, state)
            except Exception as exc:
                logger.error("Debate %s: stage %s failed: %s", context.debate_id, stage.name, exc)
                raise
            
            if settings.STAGED_DECISION_PIPELINE and not context.is_resume and stage.name == "critique":
                logger.info("Debate %s: STAGED_DECISION_PIPELINE active. Pausing after critique stage.", context.debate_id)
                state.status = "perspectives_ready"
                return state
                
        state.status = "completed"
        return state
