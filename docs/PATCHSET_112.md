# Patchset 112 — Performance and Reliability Follow-through

## Summary

This patchset implements the "Adopt" and "Adopt with Modification" items from the Review Triage document, focusing on measured improvements without regressing recent fixes.

## Changes

### Backend

#### A1) Database Query Audit + Index Verification

- **Finding**: Existing indexes are well-designed. Added one new composite index.
- **Migration**: `p112_add_debate_user_status_created_index.py`
  - Adds `ix_debate_user_status_created (user_id, status, created_at)` for ORDER BY optimization in `list_debates`
- **Files**: `alembic/versions/p112_*.py`

#### A3) Redis Connection Pooling

- **New module**: `redis_pool.py` — Centralized Redis connection pooling
  - `get_sync_redis_client()` — Shared sync pool (20 connections)
  - `get_async_redis_client()` — Shared async pool (50 connections)
  - Graceful fallback if pool creation fails
- **Updated modules**:
  - `ratelimit.py` — Uses shared sync pool
  - `sse_backend.py` — Uses shared async pool
  - `routes/debates.py` — Uses shared pool for count caching
- **Metrics added**: `redis.pool.sync.created`, `redis.pool.async.created`, `redis.pool.sync.failed`, `redis.pool.async.failed`

#### Observability Extensions

- **Extended `metrics.py`** with new metric names:
  - Mode usage: `mode.debate.conversation.started`, `mode.debate.started`, `mode.debate.compare.started`
  - Timeline: `timeline.fetch.slow`, `timeline.fetch.ok`
  - Redis pool: `redis.pool.*`
- **routes/debates.py**: Added mode tracking and timeline performance metrics

### Frontend

#### A4) Bundle Analysis + Import Optimization

- **next.config.ts**: Added `experimental.optimizePackageImports` for:
  - `lucide-react` (icon library)
  - `date-fns` (date utilities)
  - `@radix-ui/react-icons`
- **package.json**: Added `build:analyze` script (`ANALYZE=true npm run build`)

#### B7) React Query Policy Tuning

- **app/providers.tsx**: Tuned QueryClient defaults:
  - Added 429 (rate limit) to non-retryable errors
  - Added `refetchOnReconnect: 'always'` for live data consistency
  - Added global mutation error handler for rate limits
  - Improved TypeScript types (removed `any`)

#### A5) Accessibility Improvements

- **VotingChamber.tsx**:
  - Added `role="region"` and `aria-label="Voting Chamber"`
  - Added screen reader announcements via `aria-live="assertive"` region
  - Announces vote outcomes and individual votes for screen reader users
  - Added dark mode support classes
  - Added `aria-hidden="true"` to decorative icons

- **HansardTranscript.tsx**:
  - Improved FilterSelect with proper `htmlFor`/`id` associations
  - Added `focus-within:ring-2` for visible focus states
  - Added `aria-label` to select elements
  - Added `aria-hidden="true"` to decorative icons

### Testing

- **New test file**: `tests/test_redis_pool.py`
  - Tests pool creation, caching, failure handling
  - Tests rate limiter integration with shared pool

## Files Changed

```
apps/api/
├── redis_pool.py                          (NEW)
├── metrics.py                             (MODIFIED)
├── ratelimit.py                           (MODIFIED)
├── sse_backend.py                         (MODIFIED)
├── routes/debates.py                      (MODIFIED)
├── alembic/versions/
│   └── p112_add_debate_user_status_created_index.py  (NEW)
└── tests/
    └── test_redis_pool.py                 (NEW)

apps/web/
├── next.config.ts                         (MODIFIED)
├── package.json                           (MODIFIED)
├── app/providers.tsx                      (MODIFIED)
└── components/parliament/
    ├── VotingChamber.tsx                  (MODIFIED)
    └── HansardTranscript.tsx              (MODIFIED)
```

## Excluded (per Triage)

- Fixed-size transcript virtualization (D1 — conflicts with Patchset 109 fixes)
- Repository pattern rewrite (D2 — too invasive)
- Broad DI refactor (D3 — deferred)
- Full OpenTelemetry rollout (D4 — deferred)
- Aggressive rate-limit fingerprinting (D6 — privacy concerns)

## Verification

```bash
# Backend
cd apps/api
python -c "import redis_pool; import metrics; print('OK')"
pytest tests/test_redis_pool.py -v

# Run migration
alembic upgrade head

# Frontend
cd apps/web
npm run build:analyze  # Check bundle sizes
npm run build          # Verify no build errors
```

## Definition of Done

- [x] High-value performance bottlenecks addressed (Redis pooling, index)
- [x] Redis usage is pooled and efficient
- [x] Frontend query behavior is stable and efficient
- [x] Key live/voting surfaces improved in accessibility
- [x] No recent transcript/layout fixes regressed (no fixed-size virtualization)
- [x] Tests added for new Redis pool module
