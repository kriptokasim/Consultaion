# Patchset 134 — Findings

**Baseline SHA:** `8dea682`
**Date:** 2026-06-18
**Status:** Implementation in progress

---

## Track A — Canonical Backend Settings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-A1 | High | Two parallel settings systems | ✅ Fixed |
| 134-A2 | Medium | Overlapping field definitions | ✅ Fixed |
| 134-A3 | Medium | Integrations import from wrong source | ✅ Fixed |

## Track B — Public SSE Backend Contract

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-B1 | High | Routes access private SSE attributes | ✅ Fixed |
| 134-B2 | Medium | No public replay() method | ✅ Fixed |
| 134-B3 | Low | Test files access private attributes | ✅ Fixed |

## Track C — Oversized Route Modules

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-C1 | High | debates.py 2054 lines with 60 inline imports | ✅ Fixed |
| 134-C2 | Medium | admin.py 1342 lines with 24 inline imports | ✅ Fixed |

## Track D — Oversized Frontend Components

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-D1 | High | RunDetailClient.tsx 798 lines | ✅ Fixed |

## Track E — Async Blocking Audit

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-E1 | Medium | No async blocking audit tool exists | ✅ Fixed |

## Track F — Frontend Type Safety

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-F1 | High | debate: any propagates to all components | ✅ Fixed |
| 134-F2 | High | handleStreamEvent untyped | ✅ Fixed |
| 134-F3 | Medium | DebateConfig.agents/judges: any[] | ✅ Fixed |
| 134-F4 | Medium | DebateDetail.final_meta: any | ✅ Fixed |
| 134-F5 | Medium | dangerouslySetInnerHTML without sanitization | ✅ Fixed |

## Track G — Retry Stage Graph

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-G1 | High | Retry invalidation inline in routes | ✅ Fixed |

## Track H — Test Isolation

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-H1 | High | No automatic table cleanup | ✅ Fixed |
| 134-H2 | Medium | No per-worker isolation | ✅ Fixed |

## Track I — Frontend API Error Contract

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-I1 | High | No standardized error model | ✅ Fixed |
| 134-I2 | Medium | 401/403 not differentiated | ✅ Fixed |

## Track J — Correlation Context

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-J1 | High | No end-to-end correlation | ✅ Fixed |

## Track K — Markdown Rendering Security

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-K1 | High | dangerouslySetInnerHTML in 2 locations | ✅ Fixed |
| 134-K2 | Medium | No centralized SafeMarkdown component | ✅ Fixed |

## Track L — UX Quality

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-L1 | Medium | No connection state indicator | ✅ Fixed |
| 134-L2 | Medium | No completed-run loading skeleton | ✅ Fixed |
| 134-L3 | Medium | No runs empty state | ✅ Fixed |

## Track M — Accessibility

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-M1 | Medium | No axe-core accessibility tests | ✅ Fixed |
| 134-M2 | Medium | No visual regression tests | ✅ Fixed |

## Track N — SSE Load Tests

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-N1 | Medium | No SSE load smoke tests | ✅ Fixed |

## Track O — Inline Imports

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-O1 | Medium | Unnecessary inline imports | ✅ Fixed |

## Track P — JSON Contract Versioning

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-P1 | Medium | No schema_version on JSON blobs | ✅ Fixed |
| 134-P2 | Medium | No typed Pydantic schemas for JSON | ✅ Fixed |

## Track Q — Historical Comment Cleanup

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| 134-Q1 | Medium | 268 historical Patchset/FH/OT comments | ✅ Fixed |
