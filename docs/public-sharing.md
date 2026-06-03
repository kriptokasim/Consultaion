# Public Arena Run Sharing

## Overview
The public sharing feature allows owners of completed Arena runs to generate a public, read-only link that can be shared with unauthenticated users. This acts as a primary Product-Led Growth (PLG) loop by driving virality and new user acquisition from shared artifacts.

## Data Model
We use a zero-migration approach, avoiding the need for a dedicated `is_public` database column by utilizing the existing JSON column `config` on the `Debate` model.
- `debate.config["is_public"]` (boolean) tracks the public visibility status of the run.

## Permission Model
- **Ownership:** Only the creator (owner) of a debate or a system admin can toggle its public status.
- **Read Access:** 
  - If `is_public` is true, the `require_debate_access` function permits read access without raising a 401/403.
  - Endpoints fetching debate details (`GET /debates/{id}`, `GET /debates/{id}/timeline`, `GET /debates/{id}/events`) utilize `get_optional_user` to gracefully handle unauthenticated visitors when the run is public.
- **Mutation Hardening:** All modifying actions (`POST`, `PATCH`, `DELETE`) rely on `get_current_user`, strictly preventing unauthenticated mutations.

## Frontend Flow
- **ShareRunButton:** Found in the top banner of completed Arena runs. It allows owners to make the run public and copy the link.
  - Making a run public for the first time triggers a confirmation dialog to warn about sensitive information.
  - The UI state reflects whether the run is private or public.
- **RunDetailClient & ArenaRunView:**
  - `RunDetailClient` fetches the current user's profile on mount to distinguish between authenticated users and anonymous visitors.
  - Anonymous visitors are served a special lightweight header instead of the full dashboard navigation shell.
  - Anonymous visitors also see prominent CTAs at the top and bottom of the view, encouraging them to create their own run. Links include attribution parameters (e.g., `?source=public_run&ref_run={id}`).

## Backend Flow
- **Share Endpoint:** `POST /debates/{id}/share` accepts `{"is_public": true/false}` and modifies the `config` JSON field accordingly. It validates that the requester is the debate owner.
- **Metadata Generation:** Next.js `generateMetadata` dynamically queries the debate on the server side. If `is_public` is true, it injects OpenGraph and Twitter card metadata (title, description) based on the debate's prompt.

## Analytics Events
Events are tracked through the `trackEvent` wrapper in `@/lib/analytics.ts` which falls back gracefully if no analytics provider is configured.
- `arena_share_enabled`: Fired when an owner explicitly makes a run public.
- `arena_share_disabled`: Fired when an owner explicitly makes a run private.
- `arena_share_link_copied`: Fired when the public link is copied to clipboard.
- `public_run_viewed`: Fired when an unauthenticated user mounts the run detail page.
- `public_run_cta_clicked`: Fired when a public visitor clicks a conversion CTA.

## Security Considerations
- **Metadata Leakage:** `generateMetadata` checks `is_public` before rendering sensitive prompt data in `<meta>` tags. Private runs return generic metadata.
- **Write Operations:** Strict enforcement using `Depends(get_current_user)` ensures that even if a run is public, no one except the owner can manipulate it.
- **First-Time Warning:** Users are warned before making runs public to prevent unintentional data exposure.

## Future Improvements
- If public sharing becomes a central pillar of the platform, migrating `is_public` to a dedicated indexed column in PostgreSQL will allow for public galleries or trending shared runs.
- Consider introducing granular public sharing (e.g., sharing only specific model responses while hiding others).
