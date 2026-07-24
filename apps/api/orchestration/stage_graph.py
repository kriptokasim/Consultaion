"""Retry stage graph module.

Centralized stage invalidation graph for debate retry logic.
Each stage maps to the list of stages that must be invalidated when retrying from that stage.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set


class StageKey(str, Enum):
    """Canonical stage keys for the debate pipeline checkpoint system.

    Usage: StageKey.DRAFT == "draft" (StrEnum, comparable to strings).
    """
    DRAFT = "draft"
    CRITIQUE = "critique"
    JUDGE = "judge"
    DIVERGENCE_ANALYSIS = "divergence_analysis"
    SYNTHESIS = "synthesis"
    SYNTHESIS_DRAFT = "synthesis_draft"
    VERIFICATION = "verification"
    ARENA_PERSPECTIVES = "arena_perspectives"
    ARENA_SYNTHESIS_PROVISIONAL = "arena_synthesis_provisional"
    ARENA_SYNTHESIS = "arena_synthesis"


# Known stage keys
KNOWN_STAGES: Set[str] = {k.value for k in StageKey}

# Stage aliases for backward compatibility
STAGE_ALIASES: Dict[str, str] = {
    "opening": StageKey.DRAFT,
    "argument": StageKey.CRITIQUE,
    "evaluation": StageKey.JUDGE,
    "analysis": StageKey.DIVERGENCE_ANALYSIS,
    "summary": StageKey.SYNTHESIS,
    "final": StageKey.SYNTHESIS_DRAFT,
    "check": StageKey.VERIFICATION,
    "perspectives": StageKey.ARENA_PERSPECTIVES,
    "conclusion": StageKey.ARENA_SYNTHESIS,
}

# Stage invalidation graph: stage_key → list of stages to invalidate on retry
STAGE_INVALIDATION_GRAPH: Dict[str, List[str]] = {
    StageKey.DRAFT: [StageKey.DRAFT, StageKey.CRITIQUE, StageKey.JUDGE, StageKey.SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
    StageKey.CRITIQUE: [StageKey.CRITIQUE, StageKey.JUDGE, StageKey.SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
    StageKey.JUDGE: [StageKey.JUDGE, StageKey.SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
    StageKey.DIVERGENCE_ANALYSIS: [StageKey.DIVERGENCE_ANALYSIS, StageKey.SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
    StageKey.SYNTHESIS: [StageKey.SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
    StageKey.SYNTHESIS_DRAFT: [StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION, StageKey.SYNTHESIS, StageKey.ARENA_SYNTHESIS],
    StageKey.VERIFICATION: [StageKey.VERIFICATION, StageKey.SYNTHESIS, StageKey.ARENA_SYNTHESIS],
    StageKey.ARENA_PERSPECTIVES: [
        StageKey.ARENA_PERSPECTIVES,
        StageKey.ARENA_SYNTHESIS_PROVISIONAL,
        StageKey.ARENA_SYNTHESIS,
        StageKey.DIVERGENCE_ANALYSIS,
        StageKey.SYNTHESIS_DRAFT,
        StageKey.VERIFICATION,
    ],
    StageKey.ARENA_SYNTHESIS_PROVISIONAL: [
        StageKey.ARENA_SYNTHESIS_PROVISIONAL,
        StageKey.ARENA_SYNTHESIS,
        StageKey.SYNTHESIS_DRAFT,
        StageKey.VERIFICATION,
    ],
    StageKey.ARENA_SYNTHESIS: [StageKey.ARENA_SYNTHESIS, StageKey.SYNTHESIS_DRAFT, StageKey.VERIFICATION],
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
