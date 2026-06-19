"""Retry stage graph module.

Centralized stage invalidation graph for debate retry logic.
Each stage maps to the list of stages that must be invalidated when retrying from that stage.
"""

from typing import Dict, List, Set

# Known stage keys
KNOWN_STAGES: Set[str] = {
    "draft", "critique", "judge", "divergence_analysis",
    "synthesis", "synthesis_draft", "verification",
    "arena_perspectives", "arena_synthesis",
}

# Stage aliases for backward compatibility
STAGE_ALIASES: Dict[str, str] = {
    "opening": "draft",
    "argument": "critique",
    "evaluation": "judge",
    "analysis": "divergence_analysis",
    "summary": "synthesis",
    "final": "synthesis_draft",
    "check": "verification",
    "perspectives": "arena_perspectives",
    "conclusion": "arena_synthesis",
}

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


def normalize_stage_key(stage_key: str) -> str:
    """Normalize a stage key, resolving aliases."""
    return STAGE_ALIASES.get(stage_key, stage_key)


def downstream_stages(stage_key: str) -> List[str]:
    """Return stages that depend on the given stage (transitive closure)."""
    normalized = normalize_stage_key(stage_key)
    visited: Set[str] = set()
    result: List[str] = []

    def _walk(key: str) -> None:
        if key in visited:
            return
        visited.add(key)
        deps = STAGE_INVALIDATION_GRAPH.get(key, [])
        for dep in deps:
            if dep not in visited:
                result.append(dep)
            _walk(dep)

    _walk(normalized)
    return result if result else [normalized]


def validate_stage_graph() -> List[str]:
    """Validate the stage graph for consistency.

    Returns list of errors (empty if valid).
    Note: Bidirectional dependencies (A->B, B->A) are allowed and common in retry logic.
    """
    errors: List[str] = []

    # Check all stages in graph are known
    for stage in STAGE_INVALIDATION_GRAPH:
        if stage not in KNOWN_STAGES:
            errors.append(f"Unknown stage in graph: {stage}")

    # Check all known stages have entries
    for stage in KNOWN_STAGES:
        if stage not in STAGE_INVALIDATION_GRAPH:
            errors.append(f"Missing graph entry for known stage: {stage}")

    # Check for dangling references
    for stage, deps in STAGE_INVALIDATION_GRAPH.items():
        for dep in deps:
            if dep not in KNOWN_STAGES and dep != stage:
                errors.append(f"Stage {stage} references unknown stage: {dep}")

    return errors


def get_stages_to_invalidate(stage_key: str) -> List[str]:
    """Return list of stage keys that should be invalidated when retrying from stage_key."""
    normalized = normalize_stage_key(stage_key)
    if normalized not in STAGE_INVALIDATION_GRAPH:
        return [normalized]
    return STAGE_INVALIDATION_GRAPH[normalized]


# Run validation at import time
_validation_errors = validate_stage_graph()
if _validation_errors:
    import warnings
    warnings.warn(f"Stage graph validation errors: {_validation_errors}", stacklevel=2)
