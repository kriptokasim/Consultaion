# Patchset 144 Planning: Worker Hardening and Orchestration

## Overview
While Patchset 143 successfully stabilized the Arena run golden path, ensuring reliable UI rendering during degraded SSE states and guarding against schema drift, Patchset 144 must address the deeper orchestrator and Celery worker lifecycle instabilities identified during recent audits.

## 1. Task Lifecycle Policies (Soft/Hard Time Limits)
Currently, workers can hang indefinitely on third-party provider timeouts or massive context parsing tasks.
- **Goal:** Implement strict Celery time limits.
- **Actions:**
  - Enforce `soft_time_limit` to raise `SoftTimeLimitExceeded` for graceful task cancellation and status updates to "failed".
  - Enforce `hard_time_limit` as a definitive kill-switch.
  - Require explicit `acks_late=True` and `reject_on_worker_lost=True` for idempotent pipeline steps to ensure crashed workers do not cause tasks to disappear from queues permanently.

## 2. Provider Timeout Budgets
Upstream LLM provider requests (e.g., Anthropic, Groq, OpenAI) must have bounded execution guarantees that respect the user-facing budget.
- **Goal:** Unify timeout definitions across `model_gateway`.
- **Actions:**
  - Define `timeout_budget` per model capability inside the `ModelRegistry`.
  - Pass the explicit timeout to `httpx.AsyncClient` calls rather than relying on global defaults.
  - Translate provider timeouts (e.g., HTTP 504 / 408 / TimeoutError) to well-defined `coreErrorCode` values (`"timeout"`) to power the typed frontend error boundary.

## 3. Worker Heartbeat and Zombie Auto-Remediation
The `orchestrator_cleanup.py` script currently resolves stale leases by sweeping the database. However, this relies on a passive loop.
- **Goal:** Proactive observability into worker health.
- **Actions:**
  - Add Prometheus metrics tracking Celery worker heartbeats and task saturation (active vs. queue size).
  - Tune `DEBATE_STALE_RUNNING_SECONDS` and `DEBATE_LEASE_TIMEOUT_SECONDS` based on empirical generation times to avoid aggressive premature cleanup of slow models (e.g., `gpt-4o` on long contexts).
  - Explore using Redis Pub/Sub for worker eviction events if a node is pre-empted or OOMs.

## 4. SSE Observability and Payload Sanitization
With the `streamReducer` now rejecting malformed runtime events, we must monitor the volume of these rejections.
- **Goal:** Observe and remediate SSE corruption.
- **Actions:**
  - Push `streamReducer` validation warnings (e.g., `Invalid RESPONSE_DELTA payload`) up to Sentry as frontend-captured non-fatal errors.
  - Review backend streaming dispatch for race conditions where sequences are incorrectly monotonically assigned across asynchronous Celery tasks.

## Next Steps
This document serves as the roadmap for the next development cycle. Execution should begin with a review of existing Celery configurations and HTTP gateway parameters.
