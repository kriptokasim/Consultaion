# API Contracts v2 — PS170–PS180 Additions

## Persisted Responses — `GET /debates/{id}/responses`

### New query parameter: `view`

| Value | Behavior |
|-------|----------|
| `all` (default) | All persisted response rows, backward-compatible |
| `current` | Latest response per `model_id` only (deduplicated) |
| `history` | Alias for `all` |

**Example:** `GET /debates/abc-123/responses?view=current`

### Response shape (unchanged)

```json
{
  "contract_version": 1,
  "items": [ /* PersistedModelResponse[] */ ],
  "summary": {
    "expected": 4,
    "persisted": 3,
    "successful": 3,
    "failed": 0
  }
}
```

---

## Synthesis Events — `arena_synthesis_finalized`, `arena_synthesis_revision`, `arena_synthesis_started`, `arena_synthesis`

### New fields on all synthesis event types

| Field | Type | Description |
|-------|------|-------------|
| `verification_status` | `"verified" \| "unverified" \| "failed" \| "unavailable"` | Quality gate result |
| `is_verified` | `boolean \| undefined` | `true` when `verification_status === "verified"` |
| `pipeline_type` | `"structured" \| "legacy"` | Which pipeline produced the synthesis |
| `report_version` | `number` | Schema version of the report object (currently `1`) |

### Source

- `arena_synthesis_finalized` + `arena_synthesis_revision` → extracted from `report.quality_meta.verification_status`
- `arena_synthesis_started` → `"unavailable"` until verification runs
- `arena_synthesis` (legacy) → same extraction, `pipeline_type: "legacy"` when `contract_version !== 1`

---

## Frontend State Migrations

### `SynthesisStreamingState` (synthesis reducer)

New fields:

```typescript
verificationStatus: "verified" | "unverified" | "failed" | "unavailable";
isVerified: boolean;
pipelineType: "structured" | "legacy";
reportVersion: number;
```

Initial state: `"unavailable"`, `false`, `"structured"`, `1`

### `LiveSynthesisCard`

Displays a verification status badge next to the status label when `status === "final"` and `verificationStatus` is available.

---

## Mobile UX

### Model responses — `ArenaRunView`

- **Mobile** (`< sm`): Chip selector bar (scrollable) + single visible panel below
- **Desktop** (`>= sm`): Grid layout (unchanged)

### Report sections — `ReportSection`

- `collapsible` prop: on mobile sections collapse/expand; on desktop always visible
- `defaultOpen` prop: controls initial expanded state

### Report toolbar — `DecisionReportShell`

- **Mobile**: Single `More` button with dropdown (Copy, Export, Focus Mode)
- **Desktop**: Inline buttons (unchanged)

---

## Accessibility

### Focus mode — `DecisionReportShell`

- Uses `role="dialog"` + `aria-modal="true"`
- Focus trap within dialog
- Escape key closes
- Focus restored to trigger element on close
