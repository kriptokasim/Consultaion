# Public Arena Run Sharing

## Overview
The public sharing feature allows owners of completed Arena runs to generate a public, read-only link that can be shared with unauthenticated users. This acts as a primary Product-Led Growth (PLG) loop by driving virality and new user acquisition from shared artifacts.

## Data Model
We use a zero-migration approach, avoiding the need for a dedicated `is_public` database column by utilizing the existing JSON column `config` on the `Debate` model.
- `debate.config["is_public"]` (boolean) tracks the public visibility status of the run.

## Permission Model
- **Ownership:** Only the creator (owner) of a debate or a system admin can toggle its public status.
- **Read Access:** 
  - If `is_public` is true, unauthenticated users receive a **PublicDebateDTO** (safe subset of fields).
  - Endpoints fetching debate details (`GET /debates/{id}`, `GET /debates/{id}/timeline`, `GET /debates/{id}/events`) utilize `get_optional_user` to gracefully handle unauthenticated visitors when the run is public.
  - Public events are filtered through `serialize_events_public()` to strip internal metadata.
- **Mutation Hardening:** All modifying actions (`POST`, `PATCH`, `DELETE`) rely on `get_current_user`, strictly preventing unauthenticated mutations.
  - `POST /debates/{id}/start` — requires authenticated owner/team editor via `require_debate_mutation_access()`
  - `POST /debates/{id}/share` — requires authenticated owner via `require_debate_owner()`
  - `GET /debates/{id}/report` — requires authenticated user via `get_current_user`

## Public vs Private Response

### Public Response (`PublicDebateDTO`)
Returned to unauthenticated visitors for public runs. Includes:
- `id`, `prompt`, `status`, `mode`, `created_at`, `updated_at`
- `final_content`, `is_public`, `model_id`, `routed_model`
- Safe subset of `final_meta`: `successful_count`, `total_count`, `synthesis_success`, `models`

**Excluded:** `config`, `panel_config`, `routing_meta`, `user_id`, `team_id`, `runner_id`, `engine_version`, `run_attempt`

### Private Response (`PrivateDebateDTO`)
Returned to authenticated owners/admins. Includes all fields.

## Frontend Flow
- **ShareRunButton:** Uses Radix Dialog for accessibility (focus trap, ESC close, ARIA attributes). Allows owners to toggle public status and copy the link.
  - Making a run public for the first time triggers a confirmation dialog with sensitive information warning.
  - The UI state reflects whether the run is private or public.
- **RunDetailClient & ArenaRunView:**
  - `RunDetailClient` fetches the current user's profile on mount to distinguish between authenticated users and anonymous visitors.
  - Anonymous visitors are served a special lightweight header instead of the full dashboard navigation shell.
  - Anonymous visitors see prominent CTAs:
    - **Top banner:** "Run this prompt yourself" + "Create your own run"
    - **Footer:** "Start your own Arena run" + "Run this prompt yourself" + "See how it works"
  - All CTAs include attribution parameters (`?source=public_run&ref_run={id}&intent=...`)

## Backend Flow
- **Share Endpoint:** `POST /debates/{id}/share` accepts `{"is_public": true/false}` and modifies the `config` JSON field accordingly. It validates that the requester is the debate owner.
- **Metadata Generation:** Next.js `generateMetadata` dynamically queries the debate on the server side. If `is_public` is true, it generates safe metadata using `safeMetadataTitle()` and `safeMetadataDescription()` from `lib/textSafety.ts`.

## Metadata Privacy
- Prompts are checked for sensitive patterns (API keys, emails, tokens, etc.) via `containsSensitivePattern()`
- Sensitive prompts trigger fallback to generic "Shared Arena Run | Consultaion" title
- Private and incomplete runs always get `noindex, nofollow` robots directive
- Canonical URLs are set for public run pages

## Analytics Events
Events are tracked through the `trackEvent` wrapper in `@/lib/analytics.ts` which falls back gracefully if no analytics provider is configured.
- `arena_share_enabled`: Fired when an owner explicitly makes a run public.
- `arena_share_disabled`: Fired when an owner explicitly makes a run private.
- `arena_share_link_copied`: Fired when the public link is copied to clipboard.
- `public_run_viewed`: Fired when an unauthenticated user mounts the run detail page.
- `public_run_cta_clicked`: Fired when a public visitor clicks a conversion CTA.
  - Includes `cta_location` and `intent` properties for funnel analysis.

## Security Considerations
- **DTO Serialization:** Public users receive `PublicDebateDTO` — never the full ORM object.
- **Event Filtering:** Public events are filtered to remove `seat_id`, `meta`, `debug`, `error_details`.
- **Metadata Redaction:** `safeMetadataTitle()` detects and redacts API keys, emails, tokens before embedding in meta tags.
- **Write Operations:** Strict enforcement using `Depends(get_current_user)` ensures that even if a run is public, no one except the owner can manipulate it.
- **Start Hardening:** `POST /debates/{id}/start` uses `require_debate_mutation_access()` — requires authenticated owner or team editor.
- **Report Hardening:** `GET /debates/{id}/report` requires authenticated user — never available to public.
- **First-Time Warning:** Users are warned before making runs public to prevent unintentional data exposure.

## Accessibility
- ShareRunButton uses Radix `<Dialog>` with built-in focus trap, ESC close, and ARIA attributes
- Mobile model tabs use `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`
- Error details toggle includes `aria-expanded` and descriptive `aria-label`

## Future Improvements
- If public sharing becomes a central pillar of the platform, migrating `is_public` to a dedicated indexed column in PostgreSQL will allow for public galleries or trending shared runs.
- Consider introducing granular public sharing (e.g., sharing only specific model responses while hiding others).
