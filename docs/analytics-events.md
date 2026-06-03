# Analytics Event Taxonomy

## PLG Funnel Events

### `public_run_viewed`
Fired when an unauthenticated user loads a public run detail page.

| Property | Type | Description |
|---|---|---|
| `debate_id` | string | The run ID |
| `is_authenticated` | boolean | Always `false` for this event |
| `referrer` | string | `document.referrer` |

### `public_run_cta_clicked`
Fired when a public visitor clicks any conversion CTA.

| Property | Type | Description |
|---|---|---|
| `debate_id` | string | The run ID |
| `cta_location` | string | One of: `top_banner`, `top_banner_run_same`, `footer`, `footer_run_same` |
| `is_authenticated` | boolean | Always `false` |
| `intent` | string | One of: `create_own_run`, `run_same_prompt` |

## Share Events

### `arena_share_enabled`
Fired when an owner makes a run public.

| Property | Type | Description |
|---|---|---|
| `debate_id` | string | The run ID |
| `model_count` | number | Number of models in the run |
| `has_synthesis` | boolean | Whether synthesis was generated |
| `source` | string | Where the share was triggered (e.g., `arena_run_view`) |

### `arena_share_disabled`
Fired when an owner makes a run private.

| Property | Type | Description |
|---|---|---|
| `debate_id` | string | The run ID |

### `arena_share_link_copied`
Fired when the public link is copied to clipboard.

| Property | Type | Description |
|---|---|---|
| `debate_id` | string | The run ID |
| `is_public` | boolean | Current share state |

## Voting Events

### `vote_cast`
Fired when a new vote is created (backend structured log).

| Property | Type | Description |
|---|---|---|
| `conversation_id` | string | Conversation/debate ID |
| `message_id` | string | Message ID |
| `vote` | number | -1 or 1 |
| `has_reason` | boolean | Whether a reason was given |
| `has_confidence` | boolean | Whether confidence was set |

### `vote_updated`
Fired when an existing vote is modified.

| Property | Type | Description |
|---|---|---|
| `conversation_id` | string | Conversation/debate ID |
| `message_id` | string | Message ID |
| `old_vote` | number | Previous vote value |
| `new_vote` | number | New vote value |

### `vote_reason_saved`
Fired when a vote with a reason is saved.

## Billing Events

### `billing.usage.increment`
Fired on every usage increment (debates, exports, tokens).

| Property | Type | Description |
|---|---|---|
| `user_id` | string | User ID |
| `metric` | string | `debates`, `exports`, or `tokens` |
| `value` | number | Increment amount |
| `total` | number | New total |

### `billing.limit_exceeded`
Fired when a billing limit is hit.

### `usage_limit_nearing`
Fired when usage reaches 80% of a limit.

### `billing.export_blocked`
Fired when an export is blocked due to quota.

## Conversion Funnel

```
public_run_viewed
  └→ public_run_cta_clicked (top_banner | footer)
       └→ login / signup
            └→ debate created (new user's first run)
```

## Implementation Notes

- All events go through `trackEvent()` in `@/lib/analytics.ts`
- PostHog is the primary analytics provider (optional)
- Falls back to `console.info` in development
- Falls back to `navigator.sendBeacon` if PostHog isn't initialized
- Analytics errors are silently caught — never break UX
- Users can opt out via `setAnalyticsOptOut(true)`
