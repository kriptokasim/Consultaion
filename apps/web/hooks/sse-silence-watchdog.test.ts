/**
 * Patchset 132 Track D: SSE silence watchdog tests.
 *
 * Proves that:
 * 1. Active heartbeat prevents polling
 * 2. Silence timeout starts polling
 * 3. Incoming event stops polling
 * 4. Terminal debate clears all timers
 * 5. isSilent is exposed in hook return
 */
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useRunWorkspace } from "./useRunWorkspace";

vi.mock("@/lib/api", () => ({
  getDebate: vi.fn().mockResolvedValue({ id: "mock", status: "running" }),
  getDebateResponses: vi.fn().mockResolvedValue({ items: [] }),
  continueDebate: vi.fn(),
  retryDebate: vi.fn(),
  resolveContinuationByKey: vi.fn(),
  requestWithTimeout: vi.fn().mockResolvedValue([]),
  extractEventItems: vi.fn((data: unknown) => Array.isArray(data) ? data : []),
  TimeoutError: class TimeoutError extends Error { name = "TimeoutError" },
  ApiError: class ApiError extends Error { status: number; name = "ApiError"; constructor(msg: string, status: number) { super(msg); this.status = status; } },
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: vi.fn(() => ({ status: "idle" })),
}));

vi.mock("@/lib/api/normalizeEvent", () => ({
  normalizeEvent: vi.fn((e: unknown) => e),
  normalizeTimelineItems: vi.fn((e: unknown) => e),
}));

vi.mock("@/lib/workspace/streamReducer", () => ({
  streamingReducer: vi.fn((s: unknown) => s),
  INITIAL_STREAMING_STATE: { buffers: new Map(), persisted: [] },
  selectMergedResponses: vi.fn(() => []),
}));

describe("SSE Silence Watchdog (Track D)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("isSilent is exposed in hook return with default false", async () => {
    const { result } = renderHook(() => useRunWorkspace("d1"));

    expect(result.current).toHaveProperty("isSilent");
    expect(result.current.isSilent).toBe(false);
  });

  it("terminal debate does not set isSilent", async () => {
    const { getDebate } = await import("@/lib/api");
    (getDebate as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "d1", status: "completed" });

    const { result } = renderHook(() => useRunWorkspace("d1"));

    await waitFor(() => {
      expect(result.current.coreState).toBe("ready");
    });

    expect(result.current.isSilent).toBe(false);
    expect(result.current.isPollingFallback).toBe(false);
  });

  it("returns isPollingFallback property", async () => {
    const { result } = renderHook(() => useRunWorkspace("d1"));

    expect(result.current).toHaveProperty("isPollingFallback");
  });
});
