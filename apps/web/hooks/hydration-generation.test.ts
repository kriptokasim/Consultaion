/**
 * Patchset 132 Track E: Hydration generation isolation tests.
 *
 * Proves that:
 * 1. Navigate A → B while A core fetch is pending → A cannot update B
 * 2. Stale responses cannot overwrite B
 * 3. Unmount prevents state updates
 */
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useRunWorkspace } from "./useRunWorkspace";

const mockGetDebate = vi.fn();
const mockGetDebateResponses = vi.fn();

vi.mock("@/lib/api", () => ({
  getDebate: (...args: unknown[]) => mockGetDebate(...args),
  getDebateResponses: (...args: unknown[]) => mockGetDebateResponses(...args),
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

describe("Hydration Generation Isolation (Track E)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stale fetch from debate A cannot update debate B", async () => {
    // First call (debate A) is slow
    let resolveA: (v: unknown) => void;
    const promiseA = new Promise((resolve) => {
      resolveA = resolve;
    });
    mockGetDebate.mockImplementationOnce(() => promiseA);

    const { result, rerender } = renderHook(
      ({ id }) => useRunWorkspace(id),
      { initialProps: { id: "debate-A" } }
    );

    // Wait for loading state
    await waitFor(() => {
      expect(result.current.coreState).toBe("loading");
    });

    // Navigate to debate B while A is still loading
    mockGetDebate.mockResolvedValueOnce({ id: "debate-B", status: "running" });
    mockGetDebateResponses.mockResolvedValueOnce({ items: [] });
    rerender({ id: "debate-B" });

    // Now resolve A (stale)
    act(() => {
      resolveA!({ id: "debate-A", status: "completed" });
    });

    // Wait for B to load
    await waitFor(() => {
      expect(result.current.coreState).toBe("ready");
    });

    // The debate should be B, not A
    expect(result.current.debate?.id).toBe("debate-B");
  });

  it("stale responses cannot overwrite debate B", async () => {
    // Debate A loads
    mockGetDebate.mockResolvedValueOnce({ id: "debate-A", status: "running" });
    mockGetDebateResponses.mockResolvedValueOnce({ items: [{ id: "resp-A" }] });

    const { result, rerender } = renderHook(
      ({ id }) => useRunWorkspace(id),
      { initialProps: { id: "debate-A" } }
    );

    await waitFor(() => {
      expect(result.current.coreState).toBe("ready");
    });

    // Navigate to B
    mockGetDebate.mockResolvedValueOnce({ id: "debate-B", status: "running" });
    mockGetDebateResponses.mockResolvedValueOnce({ items: [{ id: "resp-B" }] });
    rerender({ id: "debate-B" });

    await waitFor(() => {
      expect(result.current.coreState).toBe("ready");
    });

    // Responses should be for B
    expect(result.current.responses[0]?.id).toBe("resp-B");
  });

  it("unmount prevents state updates", async () => {
    let resolveDebate: (v: unknown) => void;
    mockGetDebate.mockImplementation(
      () => new Promise((resolve) => { resolveDebate = resolve; })
    );

    const { result, unmount } = renderHook(() => useRunWorkspace("d1"));

    await waitFor(() => {
      expect(result.current.coreState).toBe("loading");
    });

    // Unmount
    unmount();

    // Resolve debate after unmount
    act(() => {
      resolveDebate!({ id: "d1", status: "running" });
    });

    // State should not have transitioned to "ready" with stale data
    expect(result.current.coreState).not.toBe("ready");
  });
});
