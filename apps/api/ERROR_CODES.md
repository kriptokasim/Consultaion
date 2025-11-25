# Application Error Codes

This document lists the standardized error codes returned by the API.

## Auth Errors (`401`, `403`)

| Code | Description |
|------|-------------|
| `auth.failed` | Generic authentication failure |
| `auth.invalid_credentials` | Invalid email or password |
| `auth.google_not_configured` | Google OAuth not configured on server |
| `auth.google_exchange_failed` | Failed to exchange code for token |
| `auth.google_missing_token` | Missing access token from Google |
| `auth.google_profile_failed` | Failed to fetch user profile from Google |
| `auth.google_missing_email` | Email not found in Google profile |
| `permission.denied` | Insufficient permissions for action |

## Validation Errors (`400`)

| Code | Description |
|------|-------------|
| `validation_error` | Generic validation error |
| `auth.missing_params` | Missing required parameters (e.g. code/state) |
| `auth.invalid_state` | Invalid OAuth state parameter |
| `auth.invalid_email` | Invalid email format |
| `auth.email_exists` | Email already registered |
| `auth.password_too_short` | Password does not meet complexity requirements |
| `debate.invalid_model` | Invalid or unavailable model ID |
| `debate.invalid_panel_config` | Invalid panel configuration |
| `debate.invalid_provider` | Unknown provider key |
| `debate.invalid_role` | Unknown role profile |
| `debate.manual_start_disabled` | Manual start is disabled by configuration |
| `debate.already_started` | Debate is not in queued state |

## Not Found Errors (`404`)

| Code | Description |
|------|-------------|
| `not_found` | Generic resource not found |
| `leaderboard.persona_not_found` | Persona not found in leaderboard |
| `debate.not_found` | Debate not found |
| `team.not_found` | Team not found |
| `scores.not_found` | No scores found for debate |

## Rate Limit Errors (`429`)

| Code | Description |
|------|-------------|
| `rate_limit.exceeded` | Too many requests |
| `rate_limit.quota_exceeded` | Billing quota exceeded |

## Service Errors (`503`)

| Code | Description |
|------|-------------|
| `service.circuit_open` | Service temporarily unavailable |
| `models.unavailable` | No AI models configured |

## Conflict Errors (`409`)

| Code | Description |
|------|-------------|
| `debate.not_finished` | Debate is still in progress |
