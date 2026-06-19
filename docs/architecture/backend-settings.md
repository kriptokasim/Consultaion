# Backend Settings Architecture

## Overview

The backend uses a single canonical settings source at `apps/api/config.py` via the `AppSettings` Pydantic model.

## Canonical Source

- **File:** `apps/api/config.py`
- **Model:** `AppSettings`
- **Instance:** `settings` (module-level singleton)
- **Validation:** Startup validation via `settings.validate_production()`
- **Reload:** `settings.reload_from_env()` for test overrides

## Key Properties

1. One `AppSettings` model with typed submodels for each integration
2. One runtime `settings` instance
3. One startup-validation path
4. One reload/test override path
5. No production import of `core/settings.py`
6. Secret fields are excluded from repr via `SecretStr`

## Integration Ownership

| Integration | Settings Field | Consumer Module |
|-------------|---------------|-----------------|
| Slack | `SLACK_*` | `integrations/slack.py` |
| Email | `EMAIL_*` | `integrations/email.py` |
| Giphy | `GIPHY_*` | `integrations/giphy.py` |
| PostHog | `POSTHOG_*` | `integrations/posthog.py` |
| Langfuse | `LANGFUSE_*` | `integrations/langfuse.py` |

## Lifecycle

1. **Import time:** Settings loaded from environment
2. **Startup:** `validate_production()` called
3. **Runtime:** Settings read via `settings.FIELD`
4. **Tests:** `reload_from_env()` with test overrides
5. **No hot-reload:** Settings are immutable at runtime

## Migration Notes

The old `core/settings.py` module is removed. All consumers now import from `config`.
