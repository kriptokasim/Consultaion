# Claim verification eval

Measures one thing: **can read-only repo tools reach the evidence that settles a
claim a model got wrong?**

This gates the evidence-layer work described in
`claude/consultaion-evidence-layer-plan-2026-09-07.md`. If the tools cannot reach
the evidence, no amount of model reasoning stacked on top will settle these
claims, and the feature is not worth building. Answering that costs a day here
instead of weeks in the product.

## Run

```bash
pip install pyyaml
python evals/claim_verification/run_eval.py            # score
python evals/claim_verification/run_eval.py --json     # machine-readable
python evals/claim_verification/run_eval.py --self-check
```

No API keys, no database, no network. It reads the repository through `git`, so
it works on any checkout and pins historical cases to their commits.

## Current result

```
4/6 settled, 2 need another oracle, 0 wrong
model-asserted wrong claims caught: 3/4

  repo       4/4 settled by read-only repo tools
  web        0/1
  execution  0/1
```

Read that as: **the cheapest, lowest-risk tier settles four of six claims and
catches three of the four a model actually asserted wrongly.** Adding a web
fetch would settle a fifth; only the sixth needs code execution, which is the
expensive, high-risk tier. The build order in the plan follows directly.

## Where the cases come from

Every case is a claim made during the 2026-09-07 working session on this
repository — by Claude, by ChatGPT, or implied by the design — together with the
answer that turned out to be true. Two are claims a model asserted confidently
and wrongly, which is what makes this a test rather than a demo:

| Case | Claimed by | Truth |
|---|---|---|
| All arena seats are one free model | Claude | False — `SOTA_ARENA_MODELS` holds six |
| The analytics `forEach` bug is still live | Claude | False — guard landed in `3b0cfd6` |
| OpenRouter has no enterprise option | ChatGPT | False — its pricing page lists one |
| A zero-cost proxy result reads as a free route | Claude | False — overstated blast radius |
| `subscribe()` releases pubsub on all paths | design | False — the Redis exhaustion bug |
| The SDK can price a deployment name | design | False — `cost_per_token` raises |

Notice what the wrong claims have in common: each was settled in seconds by
looking, and none of them by arguing. That observation is the entire thesis
behind the verification seat.

## Adding a case

```yaml
- id: short-slug
  claim: "The claim, as it was actually stated."
  asserted_by: claude | chatgpt | implied-by-design | human
  expect: VERIFIED | REFUTED
  oracle: repo | web | execution
  commit: 31f198b        # null means "current checkout"
  note: >
    Why it was believed, and what the truth is.
  check:
    tool: grep | read_file | git_log_search | list_dir
    # one of:
    refuted_if_matches: "regex"    # contradicting evidence is present
    refuted_if_absent:  "regex"    # evidence the claim depends on is missing
```

Pin `commit` whenever the case is about historical state. Without it, a case
about a bug quietly re-scores against HEAD once the bug is fixed, and starts
reporting the opposite answer.

## The self-check exists for a reason

An eval that cannot distinguish broken from fixed scores 100% and measures
nothing. `--self-check` runs the pubsub case against both the commit where the
leak is present (`13dddf3`) and the one where it is fixed (`36b0c03`) and
requires the verdicts to differ. Run it whenever the tools or the decision rules
change.

## What this deliberately does not test

- **Whether a model picks the right tool.** Here the case names the tool. The
  next tier hands the model the tool surface and lets it choose; the score above
  is what it has to beat.
- **The synthesizer's weighting.** Whether a `REFUTED` verdict actually removes a
  claim from the final report is a separate question, and belongs with the
  `verdict` field once that ships.
- **Anything outside a repository.** Web and execution cases are recorded and
  scored as out-of-scope rather than silently dropped, so the coverage table
  stays honest about which oracles are still missing.
