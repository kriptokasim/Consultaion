import logging
from typing import Any, Dict, List, Sequence, Tuple

from .state import DebateStateManager

logger = logging.getLogger(__name__)


class FinalizationService:
    """
    Helper service for finalization logic (ranking, voting, billing).
    """
    
    @staticmethod
    def compute_rankings(scores: Sequence[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Compute Borda and Condorcet rankings from scores.
        """
        if not scores:
            return [], {"borda": {}, "condorcet": {}, "combined": {}}
            
        sorted_scores = sorted(scores, key=lambda s: s["score"], reverse=True)
        n = len(sorted_scores)
        borda = {entry["persona"]: float(n - idx - 1) for idx, entry in enumerate(sorted_scores)}
        condorcet = {entry["persona"]: 0.0 for entry in sorted_scores}

        for i in range(n):
            for j in range(i + 1, n):
                first = sorted_scores[i]
                second = sorted_scores[j]
                if first["score"] >= second["score"]:
                    condorcet[first["persona"]] += 1
                else:
                    condorcet[second["persona"]] += 1

        combined = {
            persona: borda[persona] + condorcet[persona]
            for persona in borda
        }

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
    def persist_vote(state_manager: DebateStateManager, ranking: List[str], details: Dict[str, Any]):
        """
        Persist the vote result using the state manager.
        """
        state_manager.save_vote(
            method="borda+condorcet",
            ranking=ranking,
            details=details
        )
