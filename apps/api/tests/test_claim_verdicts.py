"""The verdict seam ships before the verifier, so its contract is what gets tested.

Two properties matter more than the rest:

1. With no verifier wired, synthesis is unchanged. That is what makes this
   shippable ahead of the feature, and the property that will quietly rot first.
2. A REFUTED claim never reaches consensus grouping — the entire reason the seam
   exists. Models that share a false premise agree with each other, and consensus
   is the pipeline's main confidence signal, so a false claim allowed through
   does not just add noise, it acquires corroboration.
"""
from __future__ import annotations

import pytest

from reporting.claim_verdicts import (
    UNCHECKED,
    Verdict,
    VerdictStatus,
    partition_by_verdict,
    verdict_summary,
    verify_claims,
)

pytestmark = [pytest.mark.anyio, pytest.mark.timeout(10)]


def _claim(text: str, model: str = "A", status: VerdictStatus | None = None):
    claim = {"claim": text, "model": model}
    if status is not None:
        claim["verdict"] = Verdict(status=status, evidence="e", source="s").to_dict()
    return claim


# --- the no-op guarantee ------------------------------------------------------

async def test_default_run_leaves_claims_untouched():
    claims = [_claim("a"), _claim("b", "B"), _claim("c", "C")]

    verified = await verify_claims(claims)
    kept, refuted = partition_by_verdict(verified)

    assert refuted == []
    assert [c["claim"] for c in kept] == ["a", "b", "c"]
    assert [c["model"] for c in kept] == ["A", "B", "C"]
    assert all(c["verdict"]["status"] == "UNCHECKABLE" for c in kept)


async def test_verify_claims_does_not_mutate_its_input():
    claims = [_claim("a")]
    await verify_claims(claims)
    assert "verdict" not in claims[0], "caller's list was mutated"


async def test_enabling_the_flag_without_a_verifier_is_loud(monkeypatch, caplog):
    """Silence here would read as 'checked, found nothing' — the worst outcome."""
    monkeypatch.setattr("config.settings.CLAIM_VERIFICATION_ENABLED", True)

    with caplog.at_level("WARNING"):
        result = await verify_claims([_claim("a")], debate_id="d1")

    assert result[0]["verdict"]["status"] == "UNCHECKABLE"
    assert any("no verifier is wired" in r.message for r in caplog.records)


# --- the weighting rule -------------------------------------------------------

def test_refuted_claims_are_dropped_before_grouping():
    claims = [
        _claim("true thing", "A", VerdictStatus.VERIFIED),
        _claim("false thing", "B", VerdictStatus.REFUTED),
        _claim("a judgement", "C", VerdictStatus.UNCHECKABLE),
    ]

    kept, refuted = partition_by_verdict(claims)

    assert [c["claim"] for c in kept] == ["true thing", "a judgement"]
    assert [c["claim"] for c in refuted] == ["false thing"]


def test_unverifiable_is_never_treated_as_doubt():
    """Most claims in an ordinary debate are judgements.

    Penalising them would make the product reward whatever trivia happens to be
    checkable, which is the opposite of the point.
    """
    claims = [_claim(f"c{i}", "A", VerdictStatus.UNCHECKABLE) for i in range(5)]
    kept, refuted = partition_by_verdict(claims)
    assert len(kept) == 5
    assert refuted == []


def test_a_malformed_or_missing_verdict_is_not_a_refutation():
    """Fail open. A broken verdict must never silently delete a claim."""
    claims = [
        {"claim": "no verdict key", "model": "A"},
        {"claim": "verdict is None", "model": "A", "verdict": None},
        {"claim": "junk status", "model": "A", "verdict": {"status": "BANANA"}},
    ]
    kept, refuted = partition_by_verdict(claims)
    assert len(kept) == 3
    assert refuted == []


def test_refuted_claims_cannot_corroborate_each_other():
    """Two seats asserting the same false thing must not survive as consensus."""
    claims = [
        _claim("shared false premise", "A", VerdictStatus.REFUTED),
        _claim("shared false premise", "B", VerdictStatus.REFUTED),
        _claim("something real", "C", VerdictStatus.VERIFIED),
    ]
    kept, _ = partition_by_verdict(claims)
    assert [c["model"] for c in kept] == ["C"]


# --- reporting ----------------------------------------------------------------

def test_summary_counts_what_was_checked():
    claims = [
        _claim("a", "A", VerdictStatus.VERIFIED),
        _claim("b", "B", VerdictStatus.REFUTED),
        _claim("c", "C", VerdictStatus.UNCHECKABLE),
        _claim("d", "D"),
    ]
    summary = verdict_summary(claims)

    assert summary["total"] == 4
    assert summary["checked"] == 2, "UNCHECKABLE is not 'checked'"
    assert summary["counts"]["VERIFIED"] == 1
    assert summary["counts"]["REFUTED"] == 1
    assert summary["counts"]["UNCHECKABLE"] == 2
    assert summary["enabled"] is False


def test_verdict_carries_its_evidence():
    """A verdict without evidence is an opinion wearing a badge."""
    v = Verdict(
        status=VerdictStatus.REFUTED,
        evidence="model_registry.py:52 SOTA_ARENA_MODELS = [6 distinct]",
        source="repo:apps/api/parliament/model_registry.py:52",
        tool="grep",
    )
    d = v.to_dict()
    assert d["status"] == "REFUTED"
    assert d["evidence"] and d["source"] and d["tool"]
    assert d["checked_at"]


def test_the_default_verdict_says_why_it_was_not_checked():
    assert UNCHECKED.status is VerdictStatus.UNCHECKABLE
    assert UNCHECKED.reason
