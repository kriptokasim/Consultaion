# Patchset 134 — Baseline

**Starting SHA:** `22d38d0f1ee9a598805c3b9a57a7672c73c374a7`
**Date:** 2026-06-18
**Patchset 133 Status:** Complete (15 findings fixed, 19 new tests)

---

## Findings Already Closed by Patchset 133

| ID | Finding | Status |
|----|---------|--------|
| F-1 | BYOK AAD mismatch | ✅ Fixed |
| F-3 | Stripe inner commit | ✅ Fixed |
| F-4 | Stripe side effects before commit | ✅ Fixed |
| F-5 | Audit metadata mutation | ✅ Fixed |
| F-6 | Google login audit lost | ✅ Fixed |
| F-7 | Account deletion FK violation | ✅ Fixed |
| F-8 | Destructive retry | ✅ Fixed |
| F-9 | Usage limits inner commits | ✅ Fixed |
| F-10 | Frontend one-shot timeout | ✅ Fixed |
| F-11 | Schema drift | ✅ Fixed |
| F-12 | Redis SSE heartbeat attr | ✅ Fixed |
| F-13 | SQLite migration compat | ✅ Fixed |
| F-14 | Migration table name | ✅ Fixed |

---

## Remaining Patchset 134 Findings (Still Reproducible)

### Track A — Canonical Backend Settings
| ID | Severity | Finding |
|----|----------|---------|
| 134-A1 | High | Two parallel settings systems: `config.py` (106+ consumers) and `core/settings.py` (5 consumers) |
| 134-A2 | Medium | `core/settings.py` defines overlapping fields already in `config.py` |
| 134-A3 | Medium | Integrations import from `core.settings` instead of canonical `config` |

### Track B — Public SSE Backend Contract
| ID | Severity | Finding |
|----|----------|---------|
| 134-B1 | High | `replay_events` route accesses `_history`, `_lock`, `_redis` via hasattr |
| 134-B2 | Medium | No public `replay()` method on BaseSSEBackend |
| 134-B3 | Low | Test files access `_subscribers`, `_channels`, `_history` for assertions |

### Track C — Oversized Route Modules
| ID | Severity | Finding |
|----|----------|---------|
| 134-C1 | High | `debates.py` is 2,054 lines with 60 inline imports |
| 134-C2 | Medium | `admin.py` is 1,342 lines with 24 inline imports |

### Track E — Async Blocking
| ID | Severity | Finding |
|----|----------|---------|
| 134-E1 | Medium | No async blocking audit tool exists |

### Track F — Frontend Type Safety
| ID | Severity | Finding |
|----|----------|---------|
| 134-F1 | High | `debate: any` in useRunWorkspace propagates to all components |
| 134-F2 | High | `handleStreamEvent(lastEvent: any)` — entire SSE path untyped |
| 134-F3 | Medium | `DebateConfig.agents/judges: any[]` |
| 134-F4 | Medium | `DebateDetail.final_meta: any` |
| 134-F5 | Medium | `dangerouslySetInnerHTML` without sanitization (2 locations) |

### Track G — Retry Stage Graph
| ID | Severity | Finding |
|----|----------|---------|
| 134-G1 | High | Retry invalidation logic is inline in `routes/debates.py` |

### Track Q — Historical Comments
| ID | Severity | Finding |
|----|----------|---------|
| 134-Q1 | Medium | 268 historical Patchset/FH/OT comments across `apps/api/` |

---

## Implementation Priority

1. **Track A** — Settings consolidation (5 files to migrate, delete core/settings.py)
2. **Track B** — SSE backend contract (add replay(), remove private access)
3. **Track G** — Retry stage graph (extract from debates.py)
4. **Track Q** — Historical comment cleanup
5. **Track F** — Frontend type safety (high-value type fixes)
