# Frontend API Client Architecture

This document describes the canonical API client modules in the Consultaion frontend and their responsibilities.

## Modules

### `lib/apiClient.ts` — Canonical Authenticated API Client

**Use for:** All authenticated JSON API calls.

- Handles cookie-based auth (`credentials: "include"`)
- CSRF token attachment for mutations (POST/PUT/PATCH/DELETE)
- `ApiClientError` class with `toUserMessage()` for user-facing error display
- Rate limit details extraction via `getRateLimitDetails()`
- Timeout handling

```ts
import { apiRequest, ApiClientError } from "@/lib/apiClient";

const data = await apiRequest({
  method: "POST",
  path: "/debates",
  body: { prompt: "..." },
});
```

### `lib/api.ts` — Higher-Level API Hooks & Functions

**Use for:** React hooks and convenience wrappers around `apiClient`.

- `startDebate()`, `getDebate()`, `getRateLimitInfo()` — domain-specific wrappers
- Raw `EventSource` usage for SSE (legacy, prefer `lib/sse.ts` hooks)
- `ApiError` class (legacy, prefer `ApiClientError` from `apiClient.ts`)

### `lib/auth.ts` — Auth-Specific API Calls

**Use for:** Authentication endpoints only.

- `getMe()`, `login()`, `register()` — auth flow
- `fetchWithAuth()` — authenticated fetch with cookie handling
- Overlaps with `apiClient.ts` for auth requests

## Deprecation Plan

| Current Module | Action | Timeline |
|---|---|---|
| `ApiClientError` in `apiClient.ts` | **Keep as canonical** | Current |
| `ApiError` in `api.ts` | Deprecate — use `ApiClientError` | Before public beta |
| Raw `EventSource` in `api.ts` | Deprecate — use `useEventSource`/`useSessionStream` from `lib/sse.ts` | Before public beta |
| Duplicate fetch logic in `auth.ts` | Consolidate into `apiClient.ts` | Before paid launch |

## Rules

1. **New components** must use `apiRequest` from `lib/apiClient.ts`
2. **New error handling** must use `ApiClientError.toUserMessage()`
3. **No new duplicate fetch wrappers** — extend `apiClient.ts` instead
4. **SSE** must use `useEventSource` or `useSessionStream` from `lib/sse.ts`
5. **Analytics** must use `trackEvent` from `lib/analytics.ts` (dynamic PostHog import)
