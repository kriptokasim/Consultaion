# Feature Flags Reference

## Overview

Consultaion uses environment-based feature flags to enable/disable non-core features in production. This allows safe rollouts and quick disabling if issues arise.

---

## Available Flags

### `ENABLE_CONVERSATION_MODE`

**Default:** `false`  
**Type:** Boolean (`true`/`false`, `1`/`0`)

**Description:** Enables collaborative conversation mode (alternative debate format with iterative discussion).

**When Disabled:**

- `/debates` endpoint rejects `mode=conversation` requests with `feature.disabled` error
- Frontend should hide conversation mode UI

**Example:**

```bash
ENABLE_CONVERSATION_MODE=true
```

---

### `ENABLE_GIPHY`

**Default:** `false`  
**Type:** Boolean

**Description:** Enables Giphy integration for visual delights (celebration GIFs, empty state GIFs).

**When Disabled:**

- `/gifs/celebration` returns `{url: null}`
- `/gifs/empty-state` returns `{url: null}`
- Frontend should show fallback UI

**Requires:**

- `GIPHY_API_KEY` (if enabled)

**Example:**

```bash
ENABLE_GIPHY=true
GIPHY_API_KEY=your_giphy_api_key
```

---

### `ENABLE_EMAIL_SUMMARIES`

**Default:** `false`  
**Type:** Boolean

**Description:** Enables email notifications for debate summaries and completion alerts.

**When Disabled:**

- Email sending logic is skipped
- No emails sent to users

**Requires:**

- `RESEND_API_KEY` (if enabled)

**Example:**

```bash
ENABLE_EMAIL_SUMMARIES=true
RESEND_API_KEY=your_resend_api_key
```

---

### `ENABLE_SLACK_ALERTS`

**Default:** `false`  
**Type:** Boolean

**Description:** Enables Slack webhook alerts for errors, warnings, and system events.

**When Disabled:**

- `send_slack_alert()` returns early without sending
- Admin test alert gracefully handles disabled state

**Requires:**

- `SLACK_WEBHOOK_URL` (if enabled)

**Example:**

```bash
ENABLE_SLACK_ALERTS=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Frontend Feature Flags (build-time env)

The following flags are evaluated at build time in `feature-flags.ts`:

| Flag | Env Variable | Default |
|------|-------------|---------|
| `stagedDecisionPipeline` | `STAGED_DECISION_PIPELINE` | `false` |
| `stagedDecisionPipelinePublic` | `NEXT_PUBLIC_STAGED_DECISION_PIPELINE` | `false` |
| `unifiedWorkspace` | `NEXT_PUBLIC_UNIFIED_WORKSPACE` | `false` |
| `mobileWorkspaceV2` | `NEXT_PUBLIC_MOBILE_WORKSPACE_V2` | `false` |
| `jitAuth` | `NEXT_PUBLIC_JIT_AUTH` | `false` |
| `mobileReportV2` | `NEXT_PUBLIC_MOBILE_REPORT_V2` | `false` |
| `llmOperationLimits` | `ENABLE_LLM_OPERATION_LIMITS` | `false` |
| `prometheusMetrics` | `ENABLE_PROMETHEUS_METRICS` | `false` |
| `otelTracing` | `ENABLE_OTEL_TRACING` | `false` |
| `gdprSelfService` | `ENABLE_GDPR_SELF_SERVICE` | `false` |
| `statusPage` | `NEXT_PUBLIC_STATUS_PAGE` | `false` |
| `changelog` | `NEXT_PUBLIC_CHANGELOG` | `false` |
| `offlineRecovery` | `NEXT_PUBLIC_OFFLINE_RECOVERY` | `false` |

---

## Checking Feature Status

### Frontend (API Call)

```javascript
const response = await fetch('/api/v1/config/features');
const features = await response.json();

if (features.conversation_mode) {
  // Show conversation mode UI
}

if (features.staged_decision_pipeline) {
  // Enable staged decision pipeline
}
```

### Frontend (Build-time flags)

```typescript
import { isFeatureEnabled } from "@/lib/feature-flags";

if (isFeatureEnabled("unifiedWorkspace")) {
  // Show unified workspace UI
}
```

### Backend (Python)

```python
from config import settings

if settings.ENABLE_CONVERSATION_MODE:
    # Conversation mode logic
```

---

## Production Recommendations

**Conservative Rollout:**

1. Start with all flags `false`
2. Enable one feature at a time
3. Monitor for 24-48 hours
4. If stable, enable next feature

**Enable Order:**

1. `ENABLE_SLACK_ALERTS` (for monitoring)
2. `ENABLE_LLM_OPERATION_LIMITS` (cost control)
3. `ENABLE_PROMETHEUS_METRICS` (observability)
4. `ENABLE_GIPHY` (low risk, visual only)
5. `ENABLE_EMAIL_SUMMARIES` (medium risk)
6. `ENABLE_GDPR_SELF_SERVICE` (compliance)
7. `ENABLE_CONVERSATION_MODE` (high complexity)
8. `STAGED_DECISION_PIPELINE` (pipeline change)

---

## Troubleshooting

**Feature Not Working:**

1. Check environment variable is set correctly
2. Verify no typos (e.g., `ENABLE_GIPHY` not `ENABLE_GIFY`)
3. Restart service after changing env vars
4. Check logs for feature-related errors

**Frontend Shows Feature But Backend Rejects:**

- Frontend cached old `/config/features` response
- Hard refresh or clear cache
- Verify backend environment variable updated

---

**Last Updated:** June 2026 (FH45)
