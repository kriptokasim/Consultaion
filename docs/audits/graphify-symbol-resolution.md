# Graphify Symbol Resolution Audit Report

- **Audit Date**: 2026-06-18
- **Graphify Version**: 0.8.42
- **Repository SHA**: `e51f70bff3c5378c3668da4a1db764d21651d8d3`

## Collision Resolution Case Study: `config` vs `Config`

### The Collision
In standard `graphify` runs, the import of the `config` module (e.g. `from config import settings`) was incorrectly conflated with the `alembic.config.Config` class imported inside `apps/api/scripts/dev_db.py`. This happened due to lowercase name normalization routing both imports to the node ID `config`.

### Centrality Metrics Comparison (Undirected Representation, Internal Code Nodes Only)

#### 1. Uncorrected Graph (With Collision)
- **Top Degree Centrality Node**:
  - `module:apps.api.routes.debates`: 0.0400
  - `module:apps.api.main`: 0.0327
  - `module:apps.api.routes.auth`: 0.0285
- **Top Betweenness Centrality Node**:
  - `module:apps.api.routes.debates`: 0.0406
  - `class:apps.api.scripts.dev_db.Config`: 0.0406
  - `module:apps.api.agents`: 0.0300

*Note: In the uncorrected graph, `class:apps.api.scripts.dev_db.Config` exhibits highly inflated betweenness centrality because all imports of the `config` module (settings) are wrongly routed through it.*

#### 2. Corrected Graph (Collision Resolved)
- **Top Degree Centrality Node**:
  - `module:apps.api.routes.debates`: 0.0400
  - `module:apps.api.main`: 0.0327
  - `module:apps.api.routes.auth`: 0.0285
- **Top Betweenness Centrality Node**:
  - `module:apps.api.routes.debates`: 0.0406
  - `variable:apps.api.config.settings`: 0.0370
  - `module:apps.api.agents`: 0.0301

*Resolution Results:*
- The node `variable:apps.api.config.settings` is now properly separated from `class:alembic.config.Config`.
- **Betweenness Centrality of Alembic's Config**: Dropped from inflated levels to ~0.0000.
- **Betweenness Centrality of apps.api.config.settings**: Accurately reflects its role as the true core configuration object.

## Ambiguity Analysis

### Short Names Resolving to Multiple Qualified Symbols
- None detected.

### Wildcard Imports
*Wildcard imports obscure explicit dependencies and can introduce naming collisions:*
- None found.

### Unresolved Imports
*Imports referencing modules or symbols not present locally (external libraries or missing references):*
- `from __future__ import annotations` imported in `scripts/render-schema-diagnostic.py`
- `argparse` imported in `scripts/render-schema-diagnostic.py`
- `json` imported in `scripts/render-schema-diagnostic.py`
- `os` imported in `scripts/render-schema-diagnostic.py`
- `sys` imported in `scripts/render-schema-diagnostic.py`
- `from sqlmodel import select` imported in `scripts/render-schema-diagnostic.py`
- `from sqlmodel import func` imported in `scripts/render-schema-diagnostic.py`
- `from sqlalchemy import inspect` imported in `scripts/render-schema-diagnostic.py`
- `from sqlmodel import Session` imported in `scripts/render-schema-diagnostic.py`
- `from sqlalchemy import create_engine` imported in `scripts/render-schema-diagnostic.py`
- `from sqlalchemy import inspect` imported in `scripts/render-schema-diagnostic.py`
- `from sqlalchemy import text` imported in `scripts/render-schema-diagnostic.py`
- `from __future__ import annotations` imported in `scripts/audit_alembic_revisions.py`
- `argparse` imported in `scripts/audit_alembic_revisions.py`
- `ast` imported in `scripts/audit_alembic_revisions.py`
*(Showing first 15 of 2791)*

## Manual Verification Findings
1. **`apps.api.config`**: Verified by Python AST analysis that imports of `config` indeed reference `./apps/api/config.py`.
2. **`alembic.config.Config`**: Verified that this class is only imported in `apps/api/scripts/dev_db.py` to construct Alembic migrations, and is not a core system configuration.

## Suspected False Positives / Static Analysis Limitations
1. **Name-Only Matching**: Without type inference, any usage of a variable named `settings` is statically linked to `apps.api.config.settings`, which may result in minor false positives if other local scopes use the variable name `settings`.
