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
        
        from orchestration.checkpoints import run_with_checkpoint
        
        for stage in self.stages:
            logger.info("Debate %s: starting stage %s", context.debate_id, stage.name)
            
            # 1. Define input_data mapping for the stage
            if stage.name == "draft":
                input_data = {
                    "prompt": context.prompt,
                    "agents": [a.name for a in context.config.get("agents", [])] if context.config else [],
                    "model_id": context.model_id
                }
            elif stage.name == "critique":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.candidates,
                    "model_id": context.model_id
                }
            elif stage.name == "judge":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.revised_candidates or state.candidates,
                    "judges": [j.name for j in context.config.get("judges", [])] if context.config else [],
                    "model_id": context.model_id
                }
            elif stage.name == "synthesis":
                input_data = {
                    "prompt": context.prompt,
                    "candidates": state.revised_candidates or state.candidates,
                    "scores": state.scores,
                    "model_id": context.model_id
                }
            else:
                input_data = {"prompt": context.prompt}

            # 2. Define run callback
            # Use default arguments in lambda or async def to bind state
            async def run_fn(s=stage, c=context, st=state):
                return await s.run(c, st)

            # 3. Define load callback to retrieve DB entities on cache hit
            async def load_fn(session, s=stage, c=context, st=state):
                from models import Message, Score, Vote
                from sqlmodel import select
                
                if s.name == "draft":
                    stmt = select(Message).where(Message.debate_id == c.debate_id).where(Message.role == "candidate")
                    result = await session.execute(stmt)
                    messages = result.scalars().all()
                    st.candidates = [{
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    } for msg in messages]
                    st.round_index = 1
                elif s.name == "critique":
                    stmt = select(Message).where(Message.debate_id == c.debate_id).where(Message.role == "revised")
                    result = await session.execute(stmt)
                    messages = result.scalars().all()
                    st.revised_candidates = [{
                        "persona": msg.persona,
                        "text": msg.content,
                        **(msg.meta or {})
                    } for msg in messages]
                    st.round_index = 2
                elif s.name == "judge":
                    stmt = select(Score).where(Score.debate_id == c.debate_id)
                    res = await session.execute(stmt)
                    scores = res.scalars().all()
                    
                    stmt_vote = select(Vote).where(Vote.debate_id == c.debate_id)
                    res_vote = await session.execute(stmt_vote)
                    vote = res_vote.scalars().first()
                    
                    aggregated = {}
                    for detail in scores:
                        persona_entry = aggregated.setdefault(
                            detail.persona, {"persona": detail.persona, "scores": [], "rationale": detail.rationale}
                        )
                        persona_entry["scores"].append(detail.score)
                        persona_entry["rationale"] = detail.rationale
                    summary = []
                    for persona, payload in aggregated.items():
                        avg_score = sum(payload["scores"]) / max(1, len(payload["scores"]))
                        summary.append({
                            "persona": persona,
                            "score": round(avg_score, 2),
                            "rationale": payload["rationale"],
                        })
                    st.scores = summary
                    if vote:
                        st.ranking = vote.rankings.get("order") if vote.rankings else []
                        st.vote_details = vote.result
                    st.round_index = 3
                elif s.name == "synthesis":
                    stmt = select(Message).where(Message.debate_id == c.debate_id).where(Message.role == "synthesizer")
                    result = await session.execute(stmt)
                    msg = result.scalars().first()
                    if msg:
                        st.final_content = msg.content
                        if msg.meta and "synthesis_report" in msg.meta:
                            st.final_meta["synthesis_report"] = msg.meta["synthesis_report"]
                return st

            from sse_backend import get_sse_backend
            backend = get_sse_backend()
            round_map = {"draft": 1, "critique": 2, "judge": 3, "synthesis": 4}
            round_index = round_map.get(stage.name, 1)

            # Publish round_started
            await backend.publish(
                context.channel_id,
                {
                    "type": "round_started",
                    "debate_id": context.debate_id,
                    "round": round_index,
                    "stage": stage.name,
                }
            )

            import time as time_module
            from observability.metrics import record_pipeline_stage_duration, record_pipeline_stage_failure

            stage_mode = "recovery" if context.is_resume else "full"
            stage_start = time_module.monotonic()
            try:
                state = await run_with_checkpoint(
                    context.debate_id,
                    stage.name,
                    input_data,
                    run_fn,
                    load_fn
                )
                stage_elapsed = time_module.monotonic() - stage_start
                record_pipeline_stage_duration(stage.name, stage_mode, stage_elapsed)
            except Exception as exc:
                stage_elapsed = time_module.monotonic() - stage_start
                record_pipeline_stage_duration(stage.name, stage_mode, stage_elapsed)
                record_pipeline_stage_failure(stage.name, stage_mode)
                logger.error("Debate %s: stage %s failed: %s", context.debate_id, stage.name, exc)
                raise

            # Publish round_ended
            await backend.publish(
                context.channel_id,
                {
                    "type": "round_ended",
                    "debate_id": context.debate_id,
                    "round": round_index,
                    "stage": stage.name,
                }
            )
            
            if settings.STAGED_DECISION_PIPELINE and not context.is_resume and stage.name == "critique":
                logger.info("Debate %s: STAGED_DECISION_PIPELINE active. Pausing after critique stage.", context.debate_id)
                state.status = "perspectives_ready"
                return state
                
        state.status = "completed"
        return state

