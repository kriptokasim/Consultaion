# Permissions Model

## Access Levels

| Level | Description | Helper Function |
|---|---|---|
| **Public Read** | Unauthenticated access to public shared runs | `is_debate_public()` + `require_debate_access()` |
| **Authenticated Read** | Signed-in user accessing own or team debates | `require_debate_access()` |
| **Authenticated Mutation** | Signed-in user with edit rights (owner or team editor) | `require_debate_mutation_access()` |
| **Owner** | Debate creator or admin | `require_debate_owner()` |
| **Admin** | System admin with full access | `user.role == "admin"` |

## Endpoint Access Matrix

| Endpoint | Method | Auth Required | Access Level | Returns |
|---|---|---|---|---|
| `/debates` | GET | ✅ | Authenticated Read | User's debate list |
| `/debates` | POST | ✅ | Authenticated Mutation | New debate |
| `/debates/{id}` | GET | ❌ (if public) | Public Read / Authenticated Read | `PublicDebateDTO` (public) or `PrivateDebateDTO` (owner) |
| `/debates/{id}` | PATCH | ✅ | Owner | Updated debate |
| `/debates/{id}/timeline` | GET | ❌ (if public) | Public Read / Authenticated Read | Events (filtered for public) |
| `/debates/{id}/events` | GET | ❌ (if public) | Public Read / Authenticated Read | Events (filtered for public) |
| `/debates/{id}/members` | GET | ❌ (if public) | Public Read / Authenticated Read | Member list |
| `/debates/{id}/judges` | GET | ❌ (if public) | Public Read / Authenticated Read | Judge list |
| `/debates/{id}/report` | GET | ✅ | Authenticated Read | Full report |
| `/debates/{id}/start` | POST | ✅ | Authenticated Mutation (Owner) | Started debate |
| `/debates/{id}/share` | POST | ✅ | Owner | Share status |
| `/debates/{id}/export` | POST | ✅ | Authenticated Mutation | Export data |
| `/debates/{id}/scores.csv` | GET | ✅ | Authenticated Read | CSV download |
| `/debates/{id}/stream-token` | POST | ✅ | Authenticated | Stream token |
| `/debates/{id}/stream` | GET | ✅ | Authenticated (via token) | SSE stream |

## Permission Helper Reference

### `can_access_debate(debate, user, session) -> bool`
Returns True if the user can view the debate:
- User is the owner
- User is a team member
- Debate is public (`config.is_public == True`)
- User is admin

### `require_debate_access(debate, user, session) -> Debate`
Raises 404 if debate doesn't exist or user can't access it.
Used for read endpoints.

### `is_debate_public(debate) -> bool`
Returns True if `debate.config.is_public` is True.

### `is_debate_owner(debate, user) -> bool`
Returns True if user is the debate owner or an admin.

### `require_debate_owner(debate, user, session) -> Debate`
- Raises 404 if debate doesn't exist
- Raises 401 if user is not authenticated
- Raises 403 if user is not the owner or admin

### `require_debate_mutation_access(debate, user, session) -> Debate`
Like `require_debate_owner` but also allows team editors.
- Raises 404 if debate doesn't exist
- Raises 401 if user is not authenticated
- Raises 403 if user is not owner, admin, or team editor

## Public vs Private Response Comparison

### Public Response (`PublicDebateDTO`)
```json
{
  "id": "...",
  "prompt": "...",
  "status": "completed",
  "mode": "arena",
  "created_at": "...",
  "updated_at": "...",
  "final_content": "...",
  "is_public": true,
  "model_id": "...",
  "routed_model": "...",
  "successful_count": 4,
  "total_count": 4,
  "synthesis_success": true,
  "models": [...]
}
```

### Private Response (`PrivateDebateDTO`)
```json
{
  "id": "...",
  "prompt": "...",
  "status": "completed",
  "mode": "arena",
  "created_at": "...",
  "updated_at": "...",
  "final_content": "...",
  "is_public": false,
  "config": { ... },
  "panel_config": { ... },
  "routing_meta": { ... },
  "final_meta": { ... },
  "user_id": "...",
  "team_id": "...",
  "runner_id": "...",
  "engine_version": "...",
  "run_attempt": 0
}
```

## Public Event Filtering

Public events are passed through `serialize_events_public()` which:
- Keeps: `type`, `round`, `display_name`, `provider`, `content`, `text`, `logo_url`, `persona_type`, `persona_tagline`, `success`, `mode`, `at`, `model_id`
- Removes: `seat_id`, `seat_name`, `meta`, `user_id`, `team_id`, `debug`, `error_details`, `config`
