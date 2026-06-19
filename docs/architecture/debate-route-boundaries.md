# Debate Route Boundaries

## Overview

The debate routes are split into bounded context packages under `apps/api/routes/debates/`.

## Package Structure

```
apps/api/routes/debates/
├── __init__.py          # Package re-exports and router assembly
├── dependencies.py      # Shared dependencies and helpers
├── schemas.py           # Shared Pydantic schemas
├── crud.py              # CRUD operations (create, list, get, update)
├── execution.py         # Run control (start, continue, retry)
├── streaming.py         # SSE streaming and event delivery
├── exports.py           # Export functionality (CSV, reports)
├── moderation.py        # Moderation and argument tree
├── config_routes.py     # Configuration endpoints
```

## Responsibility Boundaries

| Module | Responsibility |
|--------|---------------|
| `crud.py` | Create, read, update debates; list with pagination |
| `execution.py` | Start runs, continue runs, retry agents |
| `streaming.py` | SSE event streams, replay, event queries |
| `exports.py` | CSV export, report download |
| `moderation.py` | Moderation actions, argument tree |
| `config_routes.py` | Default config, leaderboard |

## Dependency Rules

- All modules import from `dependencies.py` for shared helpers
- No circular imports between sibling modules
- Each module owns its own schemas where possible
- Shared schemas live in `schemas.py`

## Import Behavior

The `__init__.py` re-exports all public symbols for backward compatibility:

```python
from routes.debates import create_debate, list_debates, stream_events
```

## Route Registration

Routes are assembled in `__init__.py` via `router.include_router()`. The parent `routes/__init__.py` imports the assembled router.
