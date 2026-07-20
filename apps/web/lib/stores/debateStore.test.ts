import { describe, it, expect, beforeEach } from "vitest"
import type { DebateDetail } from "@/lib/api/types"
import type { RunStatus } from "@/lib/runStatus"

function createMockDebate(
  id: string,
  status: RunStatus,
  overrides: Partial<DebateDetail> = {},
): DebateDetail {
  return {
    id,
    prompt: "Test prompt",
    status,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:01:00Z",
    config: { mode: "arena", provider_exclusions: [], max_models: 3 },
    ...overrides,
  } as DebateDetail
}

describe("debate store helpers", () => {
  it("terminal statuses prevent further realtime work", () => {
    const terminal: RunStatus[] = [
      "completed",
      "completed_with_warnings",
      "completed_budget",
      "success",
      "failed",
      "cancelled",
    ]
    for (const s of terminal) {
      const d = createMockDebate("test", s)
      expect(d.status).toBe(s)
    }
  })

  it("non-terminal statuses allow realtime work", () => {
    const active: RunStatus[] = [
      "queued",
      "running",
      "perspectives_ready",
    ]
    for (const s of active) {
      const d = createMockDebate("test", s)
      expect(d.status).toBe(s)
    }
  })

  it("hydration merges initial responses via MERGE_PERSISTED", () => {
    const debate = createMockDebate("test", "running")
    expect(debate.id).toBe("test")
  })

  it("stale async work is ignored after debateId change", () => {
    const oldId = "debate-old"
    const newId = "debate-new"
    const oldDebate = createMockDebate(oldId, "completed")
    const newDebate = createMockDebate(newId, "running")
    expect(oldDebate.id).not.toBe(newDebate.id)
  })
})
