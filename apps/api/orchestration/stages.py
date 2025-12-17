import asyncio
import logging
from typing import Any, Dict, List

from agents import (
    criticize_and_revise,
    judge_scores,
    produce_candidate,
    synthesize,
)
from sse_backend import get_sse_backend

from .interfaces import DebateContext, DebateStage, DebateState
from .state import DebateStateManager

logger = logging.getLogger(__name__)


class BaseStage(DebateStage):
    """Base class with common helpers."""
    def __init__(self, state_manager: DebateStateManager):
        self.state_manager = state_manager
        self.backend = get_sse_backend()

    async def _publish(self, channel_id: str, payload: Dict[str, Any]):
        await self.backend.publish(channel_id, payload)


class DraftStage(BaseStage):
    name = "draft"

    async def run(self, context: DebateContext, state: DebateState) -> DebateState:
        round_id = await self.state_manager.start_round(1, "draft", "candidate drafting")
        
        agent_configs = context.config.get("agents", [])
        if not agent_configs:
            raise ValueError("No agents configured for draft stage")

        candidate_results = await asyncio.gather(
            *[produce_candidate(context.prompt, agent, model_id=context.model_id, debate_id=context.debate_id) 
              for agent in agent_configs],
            return_exceptions=True,
        )

        candidates: List[Dict[str, Any]] = []
        failures = []
        
        for agent, result in zip(agent_configs, candidate_results, strict=False):
            if isinstance(result, Exception):
                logger.error("Debate %s: draft seat %s failed: %s", context.debate_id, agent.name, result)
                failures.append(agent.name)
                continue
            payload, candidate_usage = result
            candidates.append(payload)
            context.usage_tracker.extend(candidate_usage)

        if failures:
            await self._publish(
                context.channel_id,
                {
                    "type": "notice",
                    "level": "warn",
                    "debate_id": context.debate_id,
                    "message": f"{len(failures)} seat(s) failed during drafting",
                },
            )

        if not candidates:
            raise RuntimeError("All candidate generators failed")

        await self.state_manager.save_messages(1, candidates, role="candidate")
        await self.state_manager.end_round(round_id)
        
        await self._publish(context.channel_id, {"type": "message", "round": 1, "candidates": candidates})
        
        state.candidates = candidates
        state.round_index = 1
        return state


class CritiqueStage(BaseStage):
    name = "critique"

    async def run(self, context: DebateContext, state: DebateState) -> DebateState:
        round_id = await self.state_manager.start_round(2, "critique", "cross-critique and revision")
        
        revised, critique_usage = await criticize_and_revise(
            context.prompt, 
            state.candidates, 
            model_id=context.model_id, 
            debate_id=context.debate_id
        )
        context.usage_tracker.extend(critique_usage)
        
        await self.state_manager.save_messages(2, revised, role="revised")
        await self.state_manager.end_round(round_id)
        
        await self._publish(context.channel_id, {"type": "message", "round": 2, "revised": revised})
        
        state.revised_candidates = revised
        state.round_index = 2
        return state


class JudgeStage(BaseStage):
    name = "judge"

    async def run(self, context: DebateContext, state: DebateState) -> DebateState:
        round_id = await self.state_manager.start_round(3, "judge", "rubric scoring")
        
        judge_configs = context.config.get("judges", [])
        candidates_to_judge = state.revised_candidates or state.candidates
        
        aggregate_scores, judge_details, judge_usage = await judge_scores(
            context.prompt, 
            candidates_to_judge, 
            judge_configs, 
            model_id=context.model_id, 
            debate_id=context.debate_id
        )
        context.usage_tracker.extend(judge_usage)
        
        await self.state_manager.save_scores(judge_details)
        await self.state_manager.end_round(round_id)
        
        await self._publish(
            context.channel_id, 
            {"type": "score", "round": 3, "scores": aggregate_scores, "judges": judge_details}
        )
        
        # Compute and persist rankings
        from .finalization import FinalizationService
        ranking, vote_details = FinalizationService.compute_rankings(aggregate_scores)
        await FinalizationService.persist_vote(self.state_manager, ranking, vote_details)
        
        state.scores = aggregate_scores
        state.ranking = ranking
        state.vote_details = vote_details
        state.round_index = 3
        return state


class SynthesisStage(BaseStage):
    name = "synthesis"

    async def run(self, context: DebateContext, state: DebateState) -> DebateState:
        # Note: Synthesis doesn't typically have its own round record in the old logic, 
        # but we might want to add one. For now, sticking to existing flow.
        
        # Logic to select candidates based on scores
        # This logic was previously in _select_candidates and _compute_rankings
        # For now, we'll assume the FinalizationService or similar helper handles the complex ranking logic
        # OR we can put it here.
        
        # Let's do a simple selection for now to match the existing flow
        candidates = state.revised_candidates or state.candidates
        scores = state.scores
        
        # Simple ranking based on score
        sorted_scores = sorted(scores, key=lambda s: s["score"], reverse=True)
        ranking = [s["persona"] for s in sorted_scores]
        
        # Select top 3
        preferred = ranking[:3]
        selected_candidates = [c for c in candidates if c["persona"] in preferred]
        if not selected_candidates:
            selected_candidates = candidates[:3]
            
        selected_scores = [s for s in scores if s["persona"] in {c["persona"] for c in selected_candidates}]
        
        final_answer, synthesis_usage = await synthesize(
            context.prompt, 
            selected_candidates, 
            selected_scores, 
            model_id=context.model_id, 
            debate_id=context.debate_id
        )
        context.usage_tracker.extend(synthesis_usage)
        
        state.final_content = final_answer
        state.ranking = ranking
        
        # We also need to save the vote/ranking to DB
        # This was done in _run_judge_round in the old code, but logically belongs after judging/before synthesis
        # We can do it here or in JudgeStage. 
        # In the old code: _compute_rankings and Vote persistence happened in _run_judge_round.
        # Let's move that back to JudgeStage or a separate VotingStage if we want to be strict.
        # For now, let's keep it simple and assume JudgeStage handles the scoring, and we handle the final selection here.
        
        return state
