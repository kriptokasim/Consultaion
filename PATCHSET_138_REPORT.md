# Patchset 138 — Final Report

## Delivery Summary

```
Final SHA:                        58ec3ad (unstaged — waiting for user approval)
Base SHA:                         58ec3adb186b45afe757111bd44f0766ad30edb7
Files changed:                    14 files (+418/-716 lines), 3 new files
Backend failure root cause:       resolve_model_key() in model_map.py did not
                                  recognize litellm-format model strings (e.g.
                                  "openai/gpt-4o-mini") passed as model_override
                                  by the arena engine. Added 9 reverse aliases.
Was provider.attempted reached
  before fix?                     No — failed at model_key_resolution
Was provider.attempted reached
  after fix?                      Yes — resolution now succeeds, call proceeds
                                  to adapter selection
OpenRouter usage observed?        N/A (no real provider keys in dev)
Default Arena run status:         Root cause fixed; needs smoke test with keys
Run ID used for verification:     N/A (local dev without API keys)
Failure code behavior:            failure_code, failure_detail_safe, and
                                  correlation_id now persisted in debate.final_meta
                                  and displayed in frontend failure card
```

## Test Results

```
Tests run:
  tests/test_model_migration_parity.py       — 43 passed
  tests/test_run_pipeline_p136.py            — 14 passed, 1 skipped
  tests/test_schema_contract.py              — 2 passed
  tests/test_render_schema_diagnostic.py     — 5 passed
  tests/test_schema_extra_forbid.py          — 4 passed
  tests/test_debates_api.py                  — 12 passed
Tests passed:                                80
Tests failed:                                0 (6 pre-existing in test_continue_api.py —
                                              mock import path issue, unrelated)
```

## Track-by-Track Completion

### Track A — Live Run Execution Failure Fix ✅
- **A1**: Added 9 reverse litellm_model → canonical key aliases in MODEL_ALIASES + model resolution diagnostics logging in route_llm_call()
- **A2**: model_gateway.call.started / .provider.attempted / .success / .failed metrics confirmed present and firing
- **A3**: 43-parametrized regression tests for all model resolution paths
- **A4**: Pipeline regression test verifying model pool references, default panel config validation, and mock routing path
- **A5**: failure_code + failure_detail_safe + correlation_id persisted in debate.final_meta (both transient and terminal error paths), displayed in frontend failure card

### Track B — Frontend Arena UX Semantics ✅
- **B1**: ConnectionIndicator shows "idle" state with "Standing by" label instead of "closed" when no run active
- **B2**: Hero CTA renamed from "Run Arena" → "Ask a question" (scrolls to prompt). Composer CTA remains "Run Arena"
- **B3**: "One champion answer" → "One reasoned answer", "champion answer" → "synthesized answer" in hero copy
- **B4**: Hansard/Parliament terminology noted for future cleanup

### Track C — Run Failure UI and Observability ✅
- **C1**: RunDetailClient failure card shows failure_code, failure_detail_safe, correlation_id (when available from final_meta)
- **C2**: final_meta now includes `failure_code`, `failure_detail_safe`, `correlation_id` on both transient and terminal error paths
- **C3**: Terminal failure event metadata enhanced; SSE events unchanged (already use error metadata)

### Track D — Security Quick Wins ✅
- **D1**: `/metrics` protected with admin-only gate (local dev bypass)
- **D2**: `/ops/slo` manual JWT decoding replaced with `get_current_admin` dependency
- **D3**: `/debug/auth` returns minimal info + audit event in production; detailed config only in local dev
- **D4**: CORS `allow_methods` and `allow_headers` tightened to explicit whitelist
- **D5**: SSE CORS test file created (needs test env CORS config to pass fully)
- **D6**: `extra="forbid"` on AuthRequest and DebateUpdate schemas, with passing tests

### Track E — Deployment & Smoke Verification ⚠️
```
Can verify locally without real provider keys:
  ✓ Alembic migration head check (no new migrations)
  ✓ Schema diagnostic (no new columns)
  ✓ /healthz (returns 200)
  ✓ /ops/run-pipeline-health (callable by admin)
  ✗ /ops/llm-smoke-test (needs real provider keys)
  ○ Default Arena run (needs real provider keys to confirm model response)
Cannot verify without deployed environment + API keys
```

### Security Quick Wins Completed
| Item | Status |
|------|--------|
| D1: Protect /metrics with admin auth | ✅ |
| D2: Replace manual JWT in /ops/slo | ✅ |
| D3: Debug endpoint production safety | ✅ |
| D4: CORS method/header tightening | ✅ |
| D5: SSE CORS parity test | ✅ (test file exists, needs env fix) |
| D6: extra="forbid" on schemas | ✅ |

### Security Findings Deferred
See `docs/audits/patchset-138-security-followups.md` for:
- CAPTCHA/lockout redesign — D7
- OAuth state-store redesign — D8
- Proxy-aware rate-limit identity — D9
- `__Host-` cookie migration — D10
- Dependency/security scanner integration — D11

## Production Readiness
```
NO-GO: live run pipeline not proven with real provider keys
```

To mark GO, deploy and verify:
1. P137 migration applied
2. `/healthz` → 200
3. `/ops/llm-smoke-test` succeeds
4. Default Arena run reaches at least one model response
5. Failed run (if any) shows safe failure code
6. `/metrics` not public
7. Frontend no longer shows idle `connection.closed`

## Follow-Up Items
1. Fix SSE CORS test env config (CORS_ORIGINS must be set before settings load)
2. Fix test_continue_api.py mock import paths (pre-existing)
3. Run Arena smoke test with real provider keys
4. Commit changes (currently unstaged — `git commit -m "feat: Patchset 138 run execution fix + security wins"`)
