from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

if TYPE_CHECKING:
    from .state import DebateStateManager

logger = logging.getLogger(__name__)


class FinalizationService:
    """
    Helper service for finalization logic (ranking, voting, billing).
    """
    
    @staticmethod
    def compute_rankings(scores: Sequence[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Compute Borda points and pairwise Condorcet wins from aggregate scores.

        Condorcet wins are the number of head-to-head score comparisons won by
        each persona. Tied scores award neither persona a win. The final order
        uses Condorcet wins first and Borda points as the deterministic
        tiebreaker.
        """
        if not scores:
            return [], {"borda": {}, "condorcet": {}, "combined": {}}

        sorted_scores = sorted(scores, key=lambda s: s["score"], reverse=True)
        n = len(sorted_scores)
        borda = {entry["persona"]: float(n - idx - 1) for idx, entry in enumerate(sorted_scores)}
        condorcet = {entry["persona"]: 0.0 for entry in sorted_scores}

        for i in range(n):
            for j in range(i + 1, n):
                a, a_score = sorted_scores[i]["persona"], sorted_scores[i]["score"]
                b, b_score = sorted_scores[j]["persona"], sorted_scores[j]["score"]
                if a_score > b_score:
                    condorcet[a] += 1.0
                elif b_score > a_score:
                    condorcet[b] += 1.0

        combined = {persona: (condorcet[persona], borda[persona]) for persona in borda}

        ranking = sorted(
            combined.keys(),
            key=lambda persona: (
                combined[persona],
                borda[persona],
                condorcet[persona],
            ),
            reverse=True,
        )

        details = {"borda": borda, "condorcet": condorcet, "combined": combined}
        return ranking, details

    @staticmethod
    async def persist_vote(state_manager: DebateStateManager, ranking: List[str], details: Dict[str, Any]):
        """
        Persist the vote result using the state manager.
        """
        await state_manager.save_vote(method="borda+condorcet", ranking=ranking, details=details)
