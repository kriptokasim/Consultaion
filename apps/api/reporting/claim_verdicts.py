"""Verdicts on extracted claims — the seam the verifier plugs into.

This module ships before the verifier does, on purpose. Every claim currently
comes back ``UNCHECKABLE``, so synthesis behaves exactly as it did; what lands
here is the schema, the weighting rule and the persistence path, tested, so that
turning on a real verifier later is a configuration change rather than surgery
through the middle of the synthesis pipeline.

Why the pipeline needs this at all: synthesis today treats agreement between
models as its main confidence signal, and agreement is least trustworthy exactly
when it matters most — when the seats share a false premise, they agree, and the
report carries maximum confidence on a wrong answer. A verdict separates "they
agree because it is true" from "they agree because they read the same thing".

Three statuses, not two. ``UNCHECKABLE`` is load-bearing: most claims in an
ordinary debate are judgements, and treating unverifiable as doubtful would make
the product reward whatever trivia happens to be checkable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Sequence, Tuple

logger = logging.getLogger("reporting.claim_verdicts")


class VerdictStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    UNCHECKABLE = "UNCHECKABLE"


@dataclass(frozen=True)
class Verdict:
    """One checked claim.

    ``evidence`` and ``source`` are not decoration. A grep can mislead and a
    fetched page can be wrong, so the reader has to be able to check the check;
    a verdict without its evidence is just another opinion wearing a badge.
    """

    status: VerdictStatus = VerdictStatus.UNCHECKABLE
    evidence: str | None = None
    source: str | None = None
    tool: str | None = None
    reason: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence": self.evidence,
            "source": self.source,
            "tool": self.tool,
            "reason": self.reason,
            "checked_at": self.checked_at.isoformat(),
        }


UNCHECKED = Verdict(reason="claim verification is not enabled")


def verification_enabled() -> bool:
    from config import settings

    return bool(getattr(settings, "CLAIM_VERIFICATION_ENABLED", False))


async def verify_claims(
    claims: Sequence[Dict[str, Any]],
    *,
    debate_id: str | None = None,
    context: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Attach a verdict to every claim. Currently a no-op.

    Returns new dicts rather than mutating in place, so a caller that keeps the
    original list is unaffected.

    The real implementation replaces the body: gate on the divergence set so only
    contested claims are checked (checking all 60 would cost more than the debate
    and slow down the mode that is meant to be fast), run the read-only tool
    surface, and turn the evidence into a status. The signature is the contract;
    nothing above it changes when that lands.
    """
    if verification_enabled():
        # Deliberately not silent: enabling the flag without an implementation
        # would otherwise look like "verification ran and found nothing".
        logger.warning(
            "CLAIM_VERIFICATION_ENABLED is on but no verifier is wired; "
            "all claims will report UNCHECKABLE (debate_id=%s)",
            debate_id or "-",
        )
    return [dict(claim, verdict=UNCHECKED.to_dict()) for claim in claims]


def _status_of(claim: Dict[str, Any]) -> VerdictStatus:
    raw = (claim.get("verdict") or {}).get("status")
    try:
        return VerdictStatus(raw)
    except ValueError:
        return VerdictStatus.UNCHECKABLE


def partition_by_verdict(
    claims: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split into (kept, refuted).

    The weighting rule, in one place:

    - ``REFUTED``    — dropped before grouping. This is the whole point: a claim
                       shown to be false must not reach consensus, and must not
                       be able to drag a second model's agreement along with it.
    - ``VERIFIED``   — kept, and carries its citation forward.
    - ``UNCHECKABLE``— kept, weighted exactly as today. Never read as doubt.

    With every claim ``UNCHECKABLE`` — the state this ships in — ``kept`` is the
    input unchanged and ``refuted`` is empty, so downstream analysis is
    bit-for-bit what it was before this module existed.
    """
    kept, refuted = [], []
    for claim in claims:
        (refuted if _status_of(claim) is VerdictStatus.REFUTED else kept).append(claim)
    return kept, refuted


def verdict_summary(claims: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts for the report, so the UI can say what was checked and what was not."""
    counts = {status.value: 0 for status in VerdictStatus}
    for claim in claims:
        counts[_status_of(claim).value] += 1
    checked = counts[VerdictStatus.VERIFIED.value] + counts[VerdictStatus.REFUTED.value]
    return {
        "counts": counts,
        "checked": checked,
        "total": len(claims),
        "enabled": verification_enabled(),
    }
