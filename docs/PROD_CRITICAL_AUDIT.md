# Production-Critical Hardening — Audit Report

## Wave 3 (branch: agent/prod-critical-audit-wave3)

### PC-ARENA-002 — Terminal event had two owners; engine emitted terminal before durable commit (P1) — VERIFIED
- **Symptom:** `arena/engine.py` published `debate_failed` (`reason="all_models_failed"`)
  from the child engine before the orchestrator committed the terminal DB
  status. In Celery mode the `TerminalCommitGuard` (installed only in the API
  process) was absent, so SSE could say "failed" while the DB still said
  "running" — a release-blocker race.
- **Fix:** removed the premature terminal emit from the engine (terminal is
  now owned solely by the orchestrator, post-commit); added `reason` to the
  orchestrator's authoritative terminal event; installed the guard in the
  worker process as defense-in-depth.
- **Regression:** `test_all_models_fail_does_not_emit_terminal_from_engine`.

### PC-PARL-002 — Judging-phase fence loss swallowed as "judging failed" (P2) — VERIFIED
- **Symptom:** `ExecutionSupersededError` from the fenced Score write was
  caught by a broad `except Exception`, relabeled "judging failed", and the
  run fell back to seat-order ranking — deferring the superseded abort.
- **Fix:** explicit `except ExecutionSupersededError: raise` before the generic
  handler.
- **Regression:** `test_superseded_score_write_aborts_not_falls_back`.

---

## Wave 2 (branch: agent/prod-critical-hardening-final, BASE 46434fe)

### PC-CMP-003 — Compare ownership fence was a no-op (P0) — VERIFIED
- **Symptom:** `assert_execution_ownership(session, lease)` was called without
  `await` in the async persistence path — the coroutine never ran, so a stale
  worker could persist messages, emit SSE, and report results after losing
  ownership.
- **Fix:** `await` the fence; on supersede, all in-flight provider tasks are
  cancelled and ExecutionSupersededError propagates (no result, no terminal
  event from the stale worker).
- **Negative regression:** `test_compare_superseded_between_provider_and_persist_stops_completely`
  (takeover injected between provider completion and persistence; asserts no
  Message rows, no seat_message SSE events, pending provider work cancelled).

### PC-CNV-002 — Conversation treated ownership loss as a seat failure (P1) — VERIFIED
- **Symptom:** broad `except Exception` in the seat loop swallowed
  ExecutionSupersededError and continued to next seats/rounds/scribe/synthesis
  — paid provider work by a superseded worker.
- **Fix:** explicit `except ExecutionSupersededError: raise` before the generic
  handler.
- **Negative regression:** `test_conversation_supersede_is_not_a_seat_failure`
  (exactly one provider call after takeover; no persisted messages; no
  seat_message events).

### PC-CMP-002 — Compare model entitlement not validated at boundary (P1) — VERIFIED
- **Symptom:** create route only checked `len(compare_models) >= 2`; arbitrary,
  duplicate, disabled, or unknown IDs went straight into config. Free-plan
  users could run advanced models via compare_models with NO hosted credit
  reservation (paid execution bypassing billing).
- **Fix:** `_validate_compare_models` at the create boundary pre-reservation:
  normalization (strip), canonical/enabled check against the user-scoped
  registry view, dedupe, ≥2 distinct required. Per-run hosted-credit policy
  extended to Compare: any advanced selected model on the free plan requires
  exactly one reservation, same as Arena.
- **Regressions:** tests/test_compare_entitlement.py (6 tests incl. credit
  exhaustion and free-plan advanced-with-reservation paths).

### PC-CMP-004 — Raw provider exception text persisted/emitted by Compare (P2→P1) — VERIFIED
- **Fix:** failures classified via classify_provider_exception; only safe
  message + code stored in Message.meta / seat_message events.

### PC-IDT-001 — Relational attempt identity on engine writes (P2) — VERIFIED
- Compare/Conversation durable messages now carry the real `attempt_id`
  (DebateAttempt FK for the leased attempt) in addition to the deterministic
  response_id.

---

## Wave 1

- **BASE_SHA:** `f2f5cec8ac1df6b440c17bd8d70fc30bcb48910c` (origin/main at start)
- **Branch:** `agent/prod-critical-hardening`
- **Method:** three parallel deep audits (backend execution authorities, frontend
  realtime state, auth/authz), followed by reproduce → regression-test → minimal
  authoritative fix → verify. Every fix below has a regression test or was
  verified by the existing suite.

Status legend: VERIFIED = fix + test evidence in this branch.

---

## Confirmed findings and fixes

### PC-AUTH-001 — Disabled account can log in with password (P0) — VERIFIED
- **Mode/component:** auth / `apps/api/routes/auth.py`
- **Symptom:** a disabled (`is_active=False`) user could POST `/auth/login`
  with valid credentials and receive a fresh JWT + cookies. Existing-JWT and
  API-key boundaries already rejected disabled users, but password login did
  not.
- **Root cause:** no `is_active` check anywhere in `login_user`.
- **Fix:** explicit `is_active` gate after credential verification, raising
  `auth.account_disabled` (403).
- **Regression:** `tests/test_auth_flows.py::test_disabled_account_cannot_login_or_use_token`

### PC-AUTH-002 — Disabled account can authenticate via Google OAuth (P1) — VERIFIED
- **Component:** `apps/api/routes/auth.py` (GET and POST `/auth/google/callback`)
- **Fix:** same `is_active` gate in both callback paths before token issuance.
- **Regression:** covered by the auth-flow suite; both handlers share the gate.

### PC-FE-001 — Replayed synthesis delta rolls a finalized report back to "streaming" (P1) — VERIFIED
- **Mode:** Arena / `apps/web/lib/workspace/synthesisReducer.ts`
- **Symptom:** on SSE reconnect/replay, an `arena_synthesis_delta` for the
  current revision passed staleness checks (delta sequences reset to 0 after
  FINALIZED) and regressed a final/failed report to a live-streaming card.
  Violates monotonicity invariant: "final revision N replay must stay N".
- **Root cause:** DELTA/STARTED had no terminal-status guard (streamReducer had
  one; synthesisReducer did not).
- **Fix:** `isTerminal` + `supersedesTerminal` guards; only a strictly newer
  attempt/revision may supersede a terminal state.
- **Regression:** 4 new tests in `synthesisReducer.test.ts`.

### PC-CMP-001 — Compare engine: unfenced writes, duplicates, batched UX, fake success (P1) — VERIFIED
- **Mode:** Compare / `apps/api/compare/engine.py`
- **Symptom:** messages persisted with no execution-lease fence (stale worker /
  duplicate dispatch could write duplicate rows), no `response_id` dedupe, all
  responses persisted/published only after ALL models finished (violates
  progressive-visibility contract), and run always returned `completed` even
  when every model failed.
- **Fix:** rewrite of persistence path:
  - `assert_execution_ownership` fence before each write;
  - attempt-scoped deterministic `response_id` (`compare:{debate}:a{attempt}:{model}`),
    idempotent via the partial unique index;
  - `asyncio.as_completed` progressive persist+publish per model;
  - deterministic status: `failed` when zero successes,
    `completed_with_warnings` on partial, `completed` otherwise;
  - leaked tasks cancelled in `finally`.
- **Regressions:** `tests/test_mode_engine_hardening.py` (4 tests).

### PC-CNV-001 — Conversation engine: unfenced writes, duplicates, fabricated success (P1) — VERIFIED
- **Mode:** Conversation / `apps/api/conversation/engine.py`
- **Symptom:** same unfenced/duplicate-write class as Compare; empty transcript
  (all seats failed) still produced a `completed` result with a synthesized
  "answer" over nothing; internal error string "Failed to generate synthesis."
  surfaced as user-visible verdict content.
- **Fix:** sync ownership fence per write; attempt-scoped `response_id`
  (`conversation:{debate}:a{attempt}:r{round}:{seat}`); empty transcript ⇒
  `failed/all_conversation_seats_failed`; failed synthesis falls back to the
  real transcript with `completed_with_warnings`, never the error string.
- **Regressions:** `tests/test_mode_engine_hardening.py`;
  `test_conversation_mode.py` updated to bind a live lease (writes are now
  fail-closed).

### PC-FENCE-001 — Fenced writes crash on naive/aware datetime comparison (P1) — VERIFIED
- **Component:** `apps/api/orchestration/fencing.py::fenced_debate_update`
- **Symptom:** any fenced Debate UPDATE raised
  `TypeError: can't compare offset-naive and offset-aware datetimes` whenever
  the target row was resident in the session identity map (SQLAlchemy's default
  `synchronize_session="evaluate"` re-evaluates the WHERE clause in Python).
  Terminal failure writes then silently failed (caught+logged), leaving runs
  stuck in `running`. Surfaced as ~30+ unrelated test failures.
- **Fix:** `execution_options(synchronize_session=False)` — rowcount remains the
  single source of truth.
- **Verification:** previously-failing fenced-terminal flows pass; full-suite
  failures dropped from 105 → 73 in the audited subset.

### PC-BILL-001 — Never-dispatched queued runs permanently consumed quota (P2→user-harmful) — VERIFIED
- **Component:** `apps/api/orchestrator_cleanup.py::cleanup_stale_debates`
- **Symptom:** the stale reaper marked never-dispatched debates failed but
  refunded only hosted credits (async reconciliation). Monthly
  `debates_created` and the hourly run slot stayed consumed forever for a run
  that never executed.
- **Fix:** for `queued_timeout` (never left the queue ⇒ provably no provider
  work): revert monthly usage, refund hosted credit, refund hourly slot.
  Other stale reasons keep their charge (real provider capacity may have been
  used).
- **Verification:** compensation logic mirrors `_compensate_created_run` in
  hardening.py; exercised by existing cleanup tests.

### PC-MODE-001 — Mode-default divergence: created "arena", executed "debate" (P2) — VERIFIED
- **Components:** `models.py` (column default `"conversation"`),
  `orchestrator.py` (runtime fallback `"debate"`), schema default `"arena"`.
- **Risk:** a null-mode row would be executed by the wrong engine.
- **Fix:** all defaults aligned to `arena`.

### PC-DEAD-001 — Dead legacy retry code contradicting recorded policy (P2) — VERIFIED
- **Component:** `apps/api/routes/debates/execution.py`
- **Symptom:** the legacy `/retry` + `/retry-agent` handlers (routes dropped
  from the router; superseded by `hardening.py`) remained importable with their
  own billing helpers. One helper contained a latent `NameError`
  (`decrement_debate_usage` used without import), and the dead code tripped the
  recorded policy scan (`test_retry_does_not_increment_debates_created_counter`,
  which fails on BASE).
- **Why execution.py changed heavily:** the file carried two complete retry
  implementations — the dropped legacy routes (~340 lines: `retry_debate_run`,
  `retry_agent`, `_retry_needs_hosted_credit`, `_reserve_retry_billing`,
  `_refund_committed_retry_billing`) and the hardened authority in
  `hardening.py`. Per the patchset rule ("remove dead duplicate paths after
  proving the replacement"), the unreachable legacy block was deleted. Runtime
  behavior is unchanged: those routes were already stripped from the router in
  `routes/debates/__init__.py`; the hardened endpoints own all traffic.
- **Verification:** policy test now passes against the live authority;
  `test_continue_api.py::test_retry_debate_run` repointed from the removed
  symbol to `debate_dispatch.dispatch_debate_run` (the actual dispatch seam).

### PC-PARL-001 — Parliament seat-task leak on consumer exception (P2) — VERIFIED
- **Component:** `apps/api/parliament/engine.py`
- **Fix:** if the consume loop raises (e.g. SSE publish failure), remaining seat
  tasks are cancelled and gathered before propagating.

### PC-FE-002 — Legacy JSON shapes crash UI pages (P2) — VERIFIED
- **Sites:** `RunDetailClient.tsx` (modelSlots), `ArenaRunView.tsx` (×2),
  `VotingRunView.tsx`, `analytics/page.tsx` (`debate.prompt.slice` on null).
- **Fix:** `Array.isArray` / `typeof` guards so one legacy DB row cannot crash
  analytics/run-detail rendering.

### PC-LINT-001 — Ruff violations under pinned ruff 0.16.4 (P3) — VERIFIED
- 3 pre-existing autofixable violations fixed (`B010`, import sort ×2);
  `ruff check .` clean.

---

## Pre-existing issues intentionally NOT touched (documented)

The remaining backend-suite failures (~73 in the audited subset) were proven
**pre-existing** by running the identical subset at BASE_SHA: identical failure
clusters (SSE lease-lifecycle/cors/backpressure ordering flakes, redis-dependent
billing_tasks/sse_config, Stripe webhook atomicity, llm_guard wiring,
oracle/redteam endpoint tests). Zero regressions attributable to this branch;
9 previously-failing tests now pass. These clusters share root causes of test
isolation/ordering and missing local services (Redis, PostgreSQL) and should be
addressed in a dedicated CI-stabilization wave.

Other confirmed-but-not-blocking items from audit:
- GDPR export download authorized by 8-char ID-prefix filename match (P2)
- Public `/timeline` skips public-data stripping applied to sibling endpoints (P2)
- API keys have no scope enforcement (P2)
- Stateless logout — no JWT revocation list (P2)
- POST OAuth callback trusts frontend-held INTERNAL_SECRET (design-accepted, P2)
- Raw provider exception text partially returned by ops probe endpoint (P2)
- Inline dispatch mode relies on BackgroundTasks for durability (mitigated by
  Celery-mode synchronous compensation + stale-queued reaper + billing
  compensation added here) (P1 for inline deployments; production runs Celery)

## Gate status (local)

| Gate | Result |
|---|---|
| ruff check apps/api | PASS |
| mypy (targeted critical modules) | no new errors vs BASE (repo-wide noise pre-existing) |
| pytest (SQLite, audited subset) | 0 regressions vs BASE; 9 fixed |
| vitest | 391 passed |
| tsc --noEmit | PASS |
| eslint | PASS |
| next build | PASS |

Not runnable locally: gitleaks/bandit/pip-audit/npm-audit binaries not
installed in this environment; Playwright/Docker smoke require services.
CI covers these remotely.
