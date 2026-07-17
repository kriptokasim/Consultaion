# PS155 — Arena Runtime Hardening

## PS155.1 — Execution Ownership and Checkpoint Fencing
- [x] Add `lease_epoch`, `execution_owner_id` to Debate model
- [x] Add `owner_id` to DebateStageCheckpoint model
- [x] Refactor `_get_runner_id()` to UUID-based
- [x] Refactor `_try_acquire_lease()` with atomic epoch increment + returning
- [x] Refactor `_heartbeat()` with epoch validation
- [x] Refactor `_release_lease()` with epoch guard
- [x] Thread epoch through `run_debate()`
- [x] Refactor `run_with_checkpoint()` with owner_id + exponential backoff
- [x] Create Alembic migration (`p155_lease_epoch_fencing.py`)
- [x] Write test_ps155_fencing.py
- [x] Commit PS155.1

## PS155.2 — Realtime Streaming Throughput
- [x] Implement `DeltaCoalescer` in sse_backend.py
- [x] Integrate coalescer into MemoryChannelBackend publish path
- [x] Add server-side accumulated_chars trust in streamReducer.ts
- [x] Write test_ps155_coalescing.py
- [x] Fix DeltaCoalescer flush_interval_ms=0 bug (or operator treating 0 as falsy)
- [x] Commit PS155.2

## PS155.3 — Provider Isolation and Model Deadlines
- [x] Remove os.environ mutation from agents.py and __init__.py
- [x] Add `resolve_api_key()` function to agents.py
- [x] Thread api_key explicitly through call chain (GatewayRequest & agent_bridge)
- [x] Add ARENA_MODEL_TOTAL_TIMEOUT_S setting (60s)
- [x] Wrap arena model calls in asyncio.wait_for()
- [x] Write test_ps155_isolation.py
- [x] Commit PS155.3

## PS155.4 — Synthesis and Voting Correctness
- [x] Replace `_extract_json_fragment()` with robust parser
- [x] Replace all regex JSON extraction across modules
- [x] Add vote integrity validation to voting_tasks.py
- [x] Convert voting_tasks.py to async DB sessions
- [x] Write test_ps155_json_parsing.py
- [x] Commit PS155.4

## PS155.5 — Worker, Frontend, and Auth Reliability
- [x] Fix DivergenceMeter.test.tsx
- [x] Fix SafeMarkdown.test.tsx
- [x] Fix errorContract.test.ts
- [x] Fix ArenaRunView fh121.test.tsx
- [x] Commit PS155.5

## PS155.6 — Benchmarks, Tests, and CI
- [x] Write test_ps155_regression.py
- [x] Write benchmarks/ps155_streaming.py
- [x] Verify ruff check (0 errors)
- [x] Verify pytest (all PS155 tests pass: 28 passed, 1 skipped)
- [x] Verify tsc --noEmit (0 errors)
- [x] Verify vitest run (278 tests passed)
- [x] Final commit PS155.6
