# Incident Report: SSE UnboundLocalError & Lease Leakage

**Date:** 2026-06-17
**Status:** Resolved
**Severity:** P0
**Author:** Antigravity

## Summary
The `GET /debates/{id}/stream` endpoint was failing with an `UnboundLocalError` on `last_seq_val` when establishing live connections. This broke the realtime update mechanism for the arena frontend. Additionally, generator cancellation was being swallowed without cleanup, leading to stream lease leakages that would eventually result in HTTP 503 errors across the platform.

## Root Cause Analysis
1. **UnboundLocalError**: The variable `last_seq_val` was referenced on line 1637 to record a reconnection metric before it was defined via the `last_sequence` parameter or header on line 1655.
2. **Lease Leakage**: The asynchronous generator `eventgen()` yielded SSE chunks but swallowed `asyncio.CancelledError`. When clients disconnected early, Python's GC deferred the generator's `finally` block execution, keeping the active stream lease alive until GC or TTL expiry.
3. **Test Inaccuracy**: Pytest failed to flag the regressions due to missing environment dependencies (`pytest-asyncio`) which caused the SSE test suite to silently skip.

## Remediation
- **FH125**: Refactored `stream_events()` to resolve and validate the `last_sequence` query/header before recording the metric.
- **FH126**: Re-raised `asyncio.CancelledError` in the generator and explicitly defined `release()` idempotency.
- **FH127**: Introduced 11 explicit regression tests covering cursor evaluation and lease lifecycle.
- **FH128**: Added `smoke-production-sse.py` for post-deploy environment verification.

## Deployment Details
**Patchset Range:** FH125–FH128
**Deployed SHA:** Pending
**Verification:**
- To verify in production, execute:
  ```bash
  export API_BASE_URL=https://api.consultaion.com
  export STREAM_TOKEN=<token>
  export TEST_DEBATE_ID=<id>
  python scripts/smoke-production-sse.py
  ```

## Follow-up Action Items
- Enforce strict test-skip checks in CI to prevent silently skipped `anyio`/`asyncio` tests.
- Reconcile `anyio` vs `asyncio` markers across the backend.
