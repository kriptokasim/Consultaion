"""
Lane router for the Coding Agent Mode.
Pure functional logic to classify request tier (0/1/2) based on input complexity
and risk keywords, and determine active lanes.
"""
from dataclasses import dataclass
from typing import Optional, Set


@dataclass
class TierResult:
    tier: int
    reason: str
    active_lanes: list[str]
    risk_signals: list[str]

# High-risk keywords that warrant deeper scrutiny (judge/verifier)
RISK_KEYWORDS = {
    "auth", "oauth", "csrf", "billing", "stripe", "payment",
    "migration", "alembic", "schema", "security", "secret",
    "credential", "provider_key", "config", ".github/workflows",
    "ci.yml", "delete", "drop", "token", "webhook"
}

@dataclass
class TierThresholds:
    moderate_file_count: int = 3
    risky_file_count: int = 7
    moderate_prompt_length: int = 200
    risky_prompt_length: int = 1000
    risk_keyword_threshold: int = 1

DEFAULT_THRESHOLDS = TierThresholds()

def classify_tier(
    file_paths: list[str],
    prompt: str,
    thresholds: Optional[TierThresholds] = None
) -> TierResult:
    """
    Classify a coding task into Tier 0, 1, or 2 based on complexity and risk.
    
    Tier 0: Trivial changes (fast lane only)
    Tier 1: Moderate changes (fast + thinking)
    Tier 2: Complex or risky changes (fast + thinking + verifier + judge)
    """
    thresh = thresholds or DEFAULT_THRESHOLDS
    prompt_lower = prompt.lower()
    
    # Check risk signals in both prompt and file paths
    found_signals: Set[str] = set()
    for kw in RISK_KEYWORDS:
        if kw in prompt_lower:
            found_signals.add(kw)
        for fp in file_paths:
            if kw in fp.lower():
                found_signals.add(kw)
                
    risk_list = sorted(list(found_signals))
    
    # Evaluate Tier 2 (Risky / Complex)
    if len(found_signals) >= thresh.risk_keyword_threshold:
        return TierResult(
            tier=2,
            reason=f"Risk signals detected: {', '.join(risk_list)}",
            active_lanes=["fast", "thinking", "verifier", "judge"],
            risk_signals=risk_list
        )
    if len(file_paths) >= thresh.risky_file_count:
        return TierResult(
            tier=2,
            reason=f"High file count ({len(file_paths)} files)",
            active_lanes=["fast", "thinking", "verifier", "judge"],
            risk_signals=risk_list
        )
    if len(prompt) >= thresh.risky_prompt_length:
        return TierResult(
            tier=2,
            reason=f"Long prompt ({len(prompt)} chars)",
            active_lanes=["fast", "thinking", "verifier", "judge"],
            risk_signals=risk_list
        )
        
    # Evaluate Tier 1 (Moderate)
    if len(file_paths) >= thresh.moderate_file_count:
        return TierResult(
            tier=1,
            reason=f"Moderate file count ({len(file_paths)} files)",
            active_lanes=["fast", "thinking"],
            risk_signals=risk_list
        )
    if len(prompt) >= thresh.moderate_prompt_length:
        return TierResult(
            tier=1,
            reason=f"Moderate prompt length ({len(prompt)} chars)",
            active_lanes=["fast", "thinking"],
            risk_signals=risk_list
        )
        
    # Default Tier 0 (Trivial)
    return TierResult(
        tier=0,
        reason="Trivial task (no risk signals, low complexity)",
        active_lanes=["fast"],
        risk_signals=risk_list
    )
