#!/usr/bin/env python3
"""Score the read-only verifier against labelled claims.

The question this answers is narrow and deliberately so: **can the Phase-1 tool
surface reach the evidence that settles a claim?** It does not run the arena, it
does not call a model, and it needs no API keys. If the tools cannot reach the
evidence, no amount of model reasoning on top will settle these claims, so this
gates the rest of the work.

A later tier can hand the same cases to a model and let it choose the tools; the
score to beat is the one printed here.

Usage:
    python evals/claim_verification/run_eval.py
    python evals/claim_verification/run_eval.py --repo /path/to/Consultaion --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tools import RepoTools  # noqa: E402

VERIFIED, REFUTED, UNCHECKABLE = "VERIFIED", "REFUTED", "UNCHECKABLE"


def _load_cases(path: Path) -> list[dict]:
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is required: pip install pyyaml")
    return yaml.safe_load(path.read_text())["cases"]


def verify(case: dict, repo_root: Path) -> tuple[str, str]:
    """Return (verdict, evidence). Repo-only: non-repo oracles are UNCHECKABLE."""
    check = case.get("check", {})
    tool = check.get("tool")

    if tool in ("web", "execution"):
        return UNCHECKABLE, f"needs the {tool} oracle; read-only repo tools cannot reach it"

    repo = RepoTools(repo_root, commit=case.get("commit"))

    if tool == "grep":
        ev = repo.grep(check["pattern"], check.get("glob", "*"))
    elif tool == "read_file":
        ev = repo.read_file(check["path"], check.get("pattern"))
    elif tool == "git_log_search":
        ev = repo.git_log_search(check["needle"], check.get("path"))
    elif tool == "list_dir":
        ev = repo.list_dir(check.get("path", "."))
    else:
        return UNCHECKABLE, f"unknown tool {tool!r}"

    if ev.error:
        return UNCHECKABLE, f"{ev.tool} failed: {ev.error}"

    # Two ways a claim gets refuted: the contradicting evidence is present, or
    # the evidence the claim depends on is absent.
    if "refuted_if_matches" in check:
        rx = re.compile(check["refuted_if_matches"], re.DOTALL)
        if ev.found and rx.search(ev.excerpt):
            return REFUTED, ev.excerpt[:400]
        if not ev.found:
            return UNCHECKABLE, "tool ran but found nothing to judge"
        return VERIFIED, ev.excerpt[:400]

    if "refuted_if_absent" in check:
        # Read the file whole so a multi-line shape can be tested.
        content, error = repo._read(check["path"])
        if content is None:
            return UNCHECKABLE, error or "unreadable"
        if re.search(check["refuted_if_absent"], content, re.DOTALL):
            return VERIFIED, "expected shape present"
        return REFUTED, f"expected shape absent from {check['path']}"

    return UNCHECKABLE, "case declares no decision rule"


# The pubsub case is the discrimination probe: the leak is present at 13dddf3 and
# fixed at 36b0c03, so a working checker must disagree with itself across them.
_PROBE = ("pubsub-released-on-all-paths", "13dddf3", REFUTED, "36b0c03", VERIFIED)


def _self_check(repo_root: Path, cases_path: Path) -> int:
    case_id, broken_at, want_broken, fixed_at, want_fixed = _PROBE
    cases = _load_cases(cases_path)
    case = next((c for c in cases if c["id"] == case_id), None)
    if case is None:
        print(f"self-check: probe case {case_id!r} is missing")
        return 1

    ok = True
    for commit, expected in ((broken_at, want_broken), (fixed_at, want_fixed)):
        probe = dict(case, commit=commit)
        got, evidence = verify(probe, repo_root)
        status = "ok" if got == expected else "MISMATCH"
        if got != expected:
            ok = False
        print(f"self-check {commit}: want {expected:<12} got {got:<12} [{status}]")
        if got != expected:
            print(f"           {evidence[:110]}")

    print("self-check: harness discriminates" if ok else "self-check: HARNESS IS NOT MEASURING ANYTHING")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--cases", default=str(Path(__file__).parent / "cases.yaml"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--self-check",
        action="store_true",
        help="Verify the harness still discriminates: the same case must come back "
        "REFUTED at the broken commit and VERIFIED at the fixed one. An eval that "
        "cannot tell those apart scores 100%% and measures nothing.",
    )
    args = ap.parse_args()

    if args.self_check:
        return _self_check(Path(args.repo), Path(args.cases))

    cases = _load_cases(Path(args.cases))
    repo_root = Path(args.repo)

    results, by_oracle = [], {}
    for case in cases:
        verdict, evidence = verify(case, repo_root)
        expected = case["expect"]
        oracle = case.get("oracle", "repo")

        if verdict == expected:
            outcome = "correct"
        elif verdict == UNCHECKABLE and oracle != "repo":
            # Honest abstention: the tool surface genuinely cannot reach this.
            outcome = "out-of-scope"
        else:
            outcome = "WRONG"

        results.append(
            {
                "id": case["id"],
                "oracle": oracle,
                "asserted_by": case.get("asserted_by", "-"),
                "expected": expected,
                "got": verdict,
                "outcome": outcome,
                "evidence": evidence,
            }
        )
        slot = by_oracle.setdefault(oracle, {"total": 0, "correct": 0})
        slot["total"] += 1
        slot["correct"] += outcome == "correct"

    if args.json:
        print(json.dumps({"results": results, "by_oracle": by_oracle}, indent=2))
        return 0 if not any(r["outcome"] == "WRONG" for r in results) else 1

    print("\nclaim verification — read-only repo tools\n" + "=" * 62)
    for r in results:
        mark = {"correct": "PASS", "out-of-scope": "n/a ", "WRONG": "FAIL"}[r["outcome"]]
        print(f"[{mark}] {r['id']:<34} {r['expected']:<12} got {r['got']}")
        if r["outcome"] != "correct":
            print(f"         {r['evidence'][:110]}")

    correct = sum(r["outcome"] == "correct" for r in results)
    wrong = sum(r["outcome"] == "WRONG" for r in results)
    oos = sum(r["outcome"] == "out-of-scope" for r in results)

    print("\ncoverage by oracle")
    for oracle, s in sorted(by_oracle.items()):
        print(f"  {oracle:<10} {s['correct']}/{s['total']} settled by read-only repo tools")

    print(f"\n{correct}/{len(results)} settled, {oos} need another oracle, {wrong} wrong")

    # Claims wrongly asserted by a model, and whether the tools catch them --
    # the number that decides whether the feature is worth building.
    model_claims = [r for r in results if r["asserted_by"] in ("claude", "chatgpt")]
    caught = sum(r["outcome"] == "correct" for r in model_claims)
    print(f"model-asserted wrong claims caught: {caught}/{len(model_claims)}")

    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
