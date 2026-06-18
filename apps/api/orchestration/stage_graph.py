"""Patchset 134 Track G: Retry stage graph module.

Centralized stage invalidation graph for debate retry logic.
Each stage maps to the list of stages that must be invalidated when retrying from that stage.
"""
from typing import Dict, List

# Stage invalidation graph: stage_key → list of stages to invalidate on retry
STAGE_INVALIDATION_GRAPH: Dict[str, List[str]] = {
    "draft": ["draft", "critique", "judge", "synthesis", "synthesis_draft", "verification"],
    "critique": ["critique", "judge", "synthesis", "synthesis_draft", "verification"],
    "judge": ["judge", "synthesis", "synthesis_draft", "verification"],
    "divergence_analysis": ["divergence_analysis", "synthesis", "synthesis_draft", "verification"],
    "synthesis": ["synthesis", "synthesis_draft", "verification"],
    "synthesis_draft": ["synthesis_draft", "verification", "synthesis", "arena_synthesis"],
    "verification": ["verification", "synthesis", "arena_synthesis"],
    "arena_perspectives": [
        "arena_perspectives",
        "arena_synthesis",
        "divergence_analysis",
        "synthesis_draft",
        "verification",
    ],
    "arena_synthesis": ["arena_synthesis", "synthesis_draft", "verification"],
}


def get_stages_to_invalidate(stage_key: str) -> List[str]:
    """Return list of stage keys that should be invalidated when retrying from stage_key."""
    return STAGE_INVALIDATION_GRAPH.get(stage_key, [stage_key])
