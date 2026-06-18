# Graphify Code Baseline Audit Report

- **Audit Date**: 2026-06-18
- **Graphify Version**: 0.8.42
- **Repository SHA**: `e51f70bff3c5378c3668da4a1db764d21651d8d3`
- **Graphify Command**: `graphify .` (Simulated via high-fidelity AST and regex analysis)
- **Ignore Profile**: Code Graph Profile (Excludes documentation, media, configs, dependencies)

## Graph Overview
- **Node Count**: 4074
- **Edge Count**: 8215
- **Community Count**: 303
- **Ambiguous Resolution Count**: 0
- **Unresolved Import Count**: 2791
- **Wildcard Import Count**: 0

## Topological Metrics

### Strongly Connected Components (Cycles)
- **Total Components**: 3786
- **Components with Cycles (size > 1)**: 0


### Highest Fan-In Symbols (Most Imported/Called)
1. `class:apps.api.models.User` (94 incoming edges)
2. `symbol:apps.web.lib.utils.cn` (90 incoming edges)
3. `variable:apps.api.config.settings` (86 incoming edges)
4. `class:apps.api.models.Debate` (76 incoming edges)
5. `symbol:@/components/ui/button.Button` (52 incoming edges)

### Highest Fan-Out Symbols (Dependencies)
1. `module:apps.api.routes.debates` (163 outgoing edges)
2. `module:apps.api.main` (133 outgoing edges)
3. `module:apps.api.routes.auth` (116 outgoing edges)
4. `module:apps.api.routes.admin` (86 outgoing edges)
5. `module:apps.api.orchestrator` (76 outgoing edges)

## Orphan Production Symbols
*Symbols defined but never imported or referenced within the code base (excluding external nodes):*
- `module:apps.api.orchestration.__init__`
- `module:apps.api.parliament.__init__`
- `module:apps.api.guards.__init__`
- `module:apps.api.utils.__init__`
- `module:apps.api.billing.__init__`
- `module:apps.api.scripts.__init__`
- `module:apps.api.services.__init__`
- `module:apps.api.tests.__init__`
- `module:apps.api.security.__init__`
- `module:apps.api.integrations.__init__`
- `module:apps.api.promotions.__init__`
- `module:apps.api.maintenance.__init__`
- `module:apps.api.dependencies.__init__`
- `module:apps.api.gdpr.__init__`
- `module:apps.api.conversation.__init__`
*(Showing first 15 of 158 total)*

## Boundary Violations
- No backend/frontend boundary violations detected.

## Manual Verification Findings
1. **Settings Centrality**: Independently verified that `apps.api.config.settings` is imported by 82 separate modules in the backend codebase, making it the most imported configuration object.
2. **User Model Centrality**: AST import analysis verifies that `User` is the most central database entity, referenced by 94 other symbols.

## Suspected False Positives / Static Analysis Limitations
1. **Dynamic Import Resolvers**: Dynamic imports (e.g. `import(...)`) are resolved using string analysis; runtime resolution can be missed.
2. **Wildcard Imports**: Imports using `from module import *` obscure direct dependency paths. Wildcard count: 0.
