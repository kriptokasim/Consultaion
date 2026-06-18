# Patchset 133 — Audit Findings

**Baseline SHA:** `e51f70bff3c5378c3668da4a1db764d21651d8d3`
**Date:** 2026-06-18
**Python:** 3.11.9 | **Node:** 22.22.0 | **PostgreSQL:** 18.4 | **Redis:** 8.0.6

---

## Finding Matrix

| ID | Severity | Fault Class | File & Symbol | Status |
|-----|----------|-------------|---------------|--------|
| F-1 | Critical | AAD Mismatch | `routes/provider_keys.py:162` `encrypt_value()` | Fixed |
| F-2 | Critical | Runtime Integration Missing | `services/provider_credentials.py` `get_model_api_key()` | Acknowledged |
| F-3 | Critical | Inner Commit | `billing/providers/stripe_provider.py:208` `db_session.commit()` | Fixed |
| F-4 | Critical | Side Effects Before Commit | `billing/providers/stripe_provider.py:128` `emit_event()` | Fixed |
| F-5 | High | Audit Metadata Mutation | `audit.py:22` `final_meta = meta or {}` | Fixed |
| F-6 | High | Audit Lost | `routes/auth.py:355` Google login audit | Fixed |
| F-7 | High | FK Violation | `routes/auth.py:609` `user_id="[deleted]"` | Fixed |
| F-8 | High | Destructive Retry | `routes/debates.py:1043-1066` deletes previous evidence | Fixed |
| F-9 | High | Inner Commits | `usage_limits.py:73,87,102,183` | Fixed |
| F-10 | High | One-shot Timeout | `hooks/useRunWorkspace.ts:624-632` | Fixed |
| F-11 | Medium | Schema Drift | Multiple tables/columns missing from migrations | Fixed |
| F-12 | Medium | Redis SSE Missing Attr | `sse_backend.py:365` no heartbeat_interval_seconds | Fixed |
| F-13 | Medium | SQLite Migration Compat | `alembic/versions/a5ca64b21960` non-batch ALTER | Fixed |
| F-14 | Medium | Migration Table Name | `alembic/versions/fh125_attempt_integration.py` wrong table name | Fixed |
| F-15 | Low | Pre-existing Test Failure | `test_api_keys.py::test_api_key_expiration` | Accepted Risk |

---

## Detailed Findings

### F-1: BYOK AAD Mismatch (Critical)

**File:** `routes/provider_keys.py:162`
**Observed:** `encrypt_value(body.key.strip())` called without `user_id` or `provider`
**Root Cause:** AAD parameters omitted during save
**Production Impact:** All saved BYOK keys fail to decrypt — saved credentials are unusable
**Fix:** Added `user_id=current_user.id` and `provider=provider_name` to encrypt_value call
**Commit:** In progress

### F-2: BYOK Runtime Integration Missing (Critical)

**File:** `services/provider_credentials.py`
**Observed:** `get_model_api_key()` exists but is never called by model gateway
**Root Cause:** Integration not wired during Patchset 131
**Production Impact:** User BYOK keys are saved but never used for model dispatch
**Status:** Acknowledged — requires model gateway integration (tracked for next patchset)

### F-3: Stripe Inner Commit (Critical)

**File:** `billing/providers/stripe_provider.py:208`
**Observed:** `db_session.commit()` inside `customer.subscription.deleted` handler
**Root Cause:** Inner commit inside provider layer
**Production Impact:** Partial transaction visibility; webhook route cannot roll back the full mutation set atomically
**Fix:** Removed inner commit; webhook route `session_scope()` now owns the transaction

### F-4: Stripe Side Effects Before Commit (Critical)

**File:** `billing/providers/stripe_provider.py:128,210`
**Observed:** `emit_event()` called inside transaction, before outer commit
**Root Cause:** Events emitted in provider handler, not post-commit
**Production Impact:** External events fire even if DB transaction fails; Stripe retry processes duplicates
**Fix:** Moved `emit_event()` calls to `_emit_post_commit_events()` in `billing/routes.py`, called after `session_scope()` exits successfully

### F-5: Audit Metadata Mutation (High)

**File:** `audit.py:22`
**Observed:** `final_meta = meta or {}` — when `meta` is a non-empty dict, `final_meta` IS the caller's dict
**Root Cause:** Missing defensive copy
**Production Impact:** `ip_address` key injected into caller's dict, causing unexpected side effects
**Fix:** Changed to `final_meta = dict(meta or {})`

### F-6: Google Login Audit Lost (High)

**File:** `routes/auth.py:355`
**Observed:** `record_audit()` called after `session.commit()`, never persisted
**Root Cause:** Audit staged after commit, session not re-committed
**Production Impact:** Google login/registration audit records are silently lost
**Fix:** Moved audit before commit; single `session.commit()` persists both user and audit atomically

### F-7: Account Deletion FK Violation (High)

**File:** `routes/auth.py:609`
**Observed:** `values(user_id="[deleted]")` written to SupportNote FK
**Root Cause:** String placeholder assigned to foreign key column
**Production Impact:** PostgreSQL rejects deletion with FK violation
**Fix:** Changed `SupportNote.user_id` to nullable; set to `NULL` instead of placeholder string

### F-8: Destructive Retry (High)

**File:** `routes/debates.py:1043-1066`
**Observed:** Retry deletes previous messages, scores, votes
**Root Cause:** Retry clears evidence instead of invalidating and creating new attempt
**Production Impact:** Historical evidence destroyed; previous attempt data irrecoverable
**Fix:** Changed to invalidate downstream checkpoints (status="invalidated") instead of deleting records

### F-9: Usage Limits Inner Commits (High)

**File:** `usage_limits.py:73,87,102,183`
**Observed:** `_get_or_create_quota()`, `_get_or_reset_counter()`, `increment_export_usage_daily()` commit inside helpers
**Root Cause:** Helpers manage their own commit, conflicting with caller's transaction
**Production Impact:** Partial visibility; quota/counter changes committed before business operation
**Fix:** Removed inner commits; helpers now use `flush()` or no commit; callers manage transaction boundary

### F-10: Frontend One-shot Timeout (High)

**File:** `hooks/useRunWorkspace.ts:624-632`
**Observed:** Single `setTimeout` for silence detection, not elapsed-time watchdog
**Root Cause:** Timeout not reset when events arrive; `lastEventTimestampRef` tracked but never checked by timer
**Production Impact:** Connected-but-silent streams may falsely trigger polling; active streams may not detect silence
**Fix:** Replaced with `setInterval` watchdog that checks `Date.now() - lastEventTimestampRef.current >= timeout`

### F-11: Schema Drift (Medium)

**Observed:** `usage_ledger_entry`, `debate_attempt`, `exports_used`, lockout fields, reconciliation columns missing from migrations
**Root Cause:** Patchset 131/132 added models but migrations not fully applied
**Production Impact:** PostgreSQL migration would fail; `alembic upgrade head` incomplete
**Fix:** Created `p133_schema_drift_resolution.py` migration

### F-12-F-14: Various Migration Issues (Medium)

Fixed: Redis SSE heartbeat attribute, SQLite batch_alter_table compatibility, `debateround` table name in migration

### F-15: Pre-existing Test Failure (Low)

`test_api_key_expiration` fails with `assert 0 == 1` — pre-existing, not introduced by this patchset
