# Security Notes

## Public Data Exposure Policy

### Principle: Public = Read-Only + Safe Subset
When a run is shared publicly, unauthenticated visitors receive a **stripped-down DTO** (`PublicDebateDTO`) that intentionally excludes:

| Excluded Field | Reason |
|---|---|
| `config` | Contains full agent/judge/budget configuration, routing params |
| `panel_config` | Contains seat configuration with potential provider details |
| `routing_meta` | Contains candidate model scores, routing decisions |
| `user_id` | Owner identity — privacy |
| `team_id` | Team affiliation — privacy |
| `runner_id` | Internal worker identifier |
| `lease_expires_at` | Internal scheduling detail |
| `last_heartbeat_at` | Internal worker health |
| `run_attempt` | Internal retry counter |
| `engine_version` | Infrastructure detail |

### Event Filtering
Public events are filtered through `serialize_events_public()` which removes:
- `seat_id` — internal seat identifier
- `meta` — raw internal metadata
- `debug` — debug information
- `error_details` — internal error messages that may contain stack traces

## Metadata Privacy

### OG/Twitter Card Metadata
- **Public runs**: Prompt text is included in metadata ONLY if it passes `containsSensitivePattern()` checks
- **Private runs**: Always use generic "Arena Run | Consultaion" title — never expose prompt
- **Incomplete runs**: Always `noindex, nofollow`
- **Sensitive prompts**: Detected patterns trigger fallback to generic "Shared Arena Run" title

### Detected Patterns
The text safety module (`utils/text_safety.py` / `lib/textSafety.ts`) detects:
1. **API keys**: OpenAI (`sk-`), Anthropic (`sk-ant-`), Google (`AIza`), Groq (`gsk_`), xAI (`xai-`)
2. **JWT tokens**: Base64-encoded three-segment tokens
3. **Bearer tokens**: `Bearer <token>` strings
4. **Credit card numbers**: 13-19 digit sequences with optional separators
5. **Secret assignments**: `PASSWORD=...`, `API_KEY=...`, etc.
6. **URLs with tokens**: URLs containing `?token=`, `?key=`, etc.
7. **Email addresses**: Standard email patterns
8. **Phone numbers**: US and international formats

## PII Scrubbing

### LLM Message Scrubbing
The `safety/pii.py` module scrubs PII from user messages before sending to LLM providers:
- Email addresses → `[redacted_email]`
- Phone numbers → `[redacted_phone]`
- Names → `[redacted_name]` (extended mode)
- Addresses → `[redacted_address]` (extended mode)

Extended mode is controlled by `PII_SCRUB_EXTENDED=1` environment variable.

### Scrubbing Metrics
The PII scrubber tracks metrics (in-memory):
- `email_count`, `phone_count`, `name_count`, `address_count`
- Accessible via `get_scrub_metrics()`, resettable via `reset_scrub_metrics()`

## Authentication Architecture

### Token Types
1. **JWT Access Token**: HS256, stored in HTTP-only cookie (`COOKIE_NAME`)
2. **API Keys**: Stored in `api_keys` table, hashed with PBKDF2
3. **Stream Tokens**: Short-lived scoped tokens for SSE connections

### Auth Flow
1. Cookie-based: `get_current_user()` reads JWT from cookie
2. Header-based: `Authorization: Bearer <token>` header fallback
3. API key: `X-API-Key` header
4. Optional: `get_optional_user()` returns None instead of 401

### Session Security
- Passwords hashed with PBKDF2 (via `hash_password()`)
- JWT expiration enforced
- Cookie `SameSite=Lax`, `HttpOnly=True`

## Mutation Hardening

### Principle: All Mutations Require Authentication
Every endpoint that modifies state uses `get_current_user` (not `get_optional_user`):
- `POST /debates` — create debate
- `POST /debates/{id}/start` — start/restart debate
- `POST /debates/{id}/share` — toggle public sharing
- `POST /debates/{id}/export` — export data
- `PATCH /debates/{id}` — update debate config

### Owner-Only Operations
These require the requesting user to be the debate owner or admin:
- `POST /debates/{id}/share` — only owner can toggle sharing
- `PATCH /debates/{id}` — only owner can modify debate config
- `POST /debates/{id}/start` — only owner/team editor can start

## Rate Limiting & Billing

### Billing Limits
- `max_debates_per_month` — enforced at debate creation
- `exports_enabled` — boolean gate on export functionality
- `max_exports_per_day` — daily export quota

### Owner Override
Users on the owner allowlist (`OWNER_EMAILS` env var) bypass:
- Billing quota checks
- Export quota checks
- Usage tracking (still tracked but limits not enforced)

## Indexing Policy

### robots.txt
- Allows `/` (public pages)
- Disallows `/admin/`, `/api/`, `/_next/`

### Per-Page Robots
- Public, completed, non-sensitive runs: `index: true, follow: true`
- Private runs: `index: false, follow: false`
- Incomplete runs: `index: false, follow: false`
- Runs with sensitive prompts: `index: false, follow: false`
