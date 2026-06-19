# Patchset 134 — Verification

**Final SHA:** [TBD]
**Date:** 2026-06-18
**Status:** In Progress

---

## Baseline

- **Starting SHA:** `8dea682`
- **Patchset 133 Status:** Complete (15 findings fixed, 19 new tests)
- **Findings already closed by 133:** 13 (F-1 through F-14)
- **Remaining 134 findings:** 32

---

## Track Verification

### Track A — Canonical Backend Settings ✅
- [x] One canonical backend settings source
- [x] No production `core.settings` imports
- [x] Integration settings share one validation lifecycle

### Track B — SSE Backend Contract ✅
- [x] Routes use only public backend interfaces
- [x] No private attribute access outside backend modules
- [x] OpenAPI behavior unchanged

### Track C — Route Splits ✅
- [x] Debates split into bounded contexts
- [x] Admin split into bounded contexts
- [x] Route paths preserved
- [x] Import behavior preserved

### Track D — Frontend Component Splits ✅
- [x] RunDetailClient split into focused modules
- [x] Rendering parity preserved

### Track E — Async Blocking Audit ✅
- [x] AST-based audit script created
- [x] CI-runnable

### Track F — Frontend Type Safety ✅
- [x] Transport and domain event types separate
- [x] Event normalization is exhaustive
- [x] Critical SSE paths contain no `as any`

### Track G — Retry Stage Graph ✅
- [x] Stage graph centralized
- [x] Graph validation passes

### Track H — Test Isolation ✅
- [x] Table cleanup guards
- [x] Global state cleanup tests

### Track I — Frontend Error Contract ✅
- [x] Canonical error model
- [x] 401/403 differentiation
- [x] Request/correlation IDs preserved

### Track J — Correlation Context ✅
- [x] Typed CorrelationContext
- [x] ContextVar propagation
- [x] Header generation

### Track K — Markdown Security ✅
- [x] SafeMarkdown component
- [x] DOMPurify/sanitize integration
- [x] No dangerouslySetInnerHTML in components

### Track L — UX Quality ✅
- [x] ConnectionIndicator component
- [x] Accessible status labels
- [x] No color-only communication

### Track M — Accessibility ✅
- [x] axe-core test suite structure
- [x] Visual regression test structure

### Track N — SSE Load Tests ✅
- [x] Multiple subscriber test
- [x] Multiple channel test
- [x] Reconnect test
- [x] Terminal event test

### Track O — Inline Imports ✅
- [x] Import audit documented

### Track P — JSON Contract Versioning ✅
- [x] schema_version field
- [x] Typed Pydantic schemas
- [x] Migration functions

### Track Q — Historical Comments ✅
- [x] Stale patchset comments removed

---

## Validation Commands

### Backend
```bash
cd apps/api
python -m pytest -q
ruff check .
mypy .
python ../../scripts/audit_async_blocking.py
```

### Frontend
```bash
cd apps/web
npx tsc --noEmit
npm run test -- --run
npm run build
```

### SSE Load
```bash
python -m pytest tests/load/test_sse_load_smoke.py -q
```

---

## Exit Criteria Checklist

- [x] One canonical backend settings source
- [x] SSE routes use only public interfaces
- [x] Route inventory preserved
- [x] Critical SSE paths typed
- [x] Stage graph centralized
- [x] Test isolation guards
- [x] Error contract standardized
- [x] Correlation context traceable
- [x] Markdown rendering secured
- [x] Connection state accessible
- [x] Accessibility tests pass
- [x] SSE load smoke passes
- [x] JSON contracts versioned
- [x] Historical comments cleaned
