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
const sseHarness = vi.hoisted(() => ({
  onEvent: null as null | ((event: unknown) => void),
  status: "idle" as "idle" | "connecting" | "connected" | "reconnecting" | "closed",
}));

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
  useEventSource: vi.fn((_url: unknown, options: { onEvent?: (event: unknown) => void }) => {
    sseHarness.onEvent = options.onEvent || null;
    return { status: sseHarness.status };
  }),
}));

vi.mock("@/lib/api/normalizeEvent", () => ({
  normalizeEvent: vi.fn((e: unknown) => e),
  normalizeTimelineItems: vi.fn((e: unknown) => e),
}));

describe("Hydration Generation Isolation (Track E)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sseHarness.onEvent = null;
    sseHarness.status = "idle";
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

  it("late structural SSE refetch from A cannot overwrite B", async () => {
    let resolveStructuralA: (value: unknown) => void;
    const structuralA = new Promise((resolve) => {
      resolveStructuralA = resolve;
    });
    mockGetDebate
      .mockResolvedValueOnce({ id: "debate-A", status: "running" })
      .mockImplementationOnce(() => structuralA)
      .mockResolvedValueOnce({ id: "debate-B", status: "running" });
    mockGetDebateResponses.mockResolvedValue({ items: [] });

    const { result, rerender } = renderHook(
      ({ id }) => useRunWorkspace(id),
      { initialProps: { id: "debate-A" } },
    );
    await waitFor(() => expect(result.current.debate?.id).toBe("debate-A"));
    const oldHandler = sseHarness.onEvent;
    expect(oldHandler).toBeTypeOf("function");

    act(() => {
      oldHandler!({ type: "stage_checkpoint", debate_id: "debate-A", payload: {} });
    });
    rerender({ id: "debate-B" });
    await waitFor(() => expect(result.current.debate?.id).toBe("debate-B"));

    await act(async () => {
      resolveStructuralA!({ id: "debate-A", status: "completed" });
      await structuralA;
    });
    expect(result.current.debate?.id).toBe("debate-B");
  });

  it("clears active streaming buffers when the run changes", async () => {
    mockGetDebate
      .mockResolvedValueOnce({ id: "debate-A", status: "running" })
      .mockResolvedValueOnce({ id: "debate-B", status: "running" });
    mockGetDebateResponses.mockResolvedValue({ items: [] });

    const { result, rerender } = renderHook(
      ({ id }) => useRunWorkspace(id),
      { initialProps: { id: "debate-A" } },
    );
    await waitFor(() => expect(result.current.debate?.id).toBe("debate-A"));

    act(() => {
      sseHarness.onEvent!({
        type: "model_response_started",
        debate_id: "debate-A",
        payload: { response_id: "response-A", model_id: "model-A" },
      });
    });
    await waitFor(() => expect(result.current.mergedStreamingResponses).toHaveLength(1));

    rerender({ id: "debate-B" });
    await waitFor(() => expect(result.current.mergedStreamingResponses).toHaveLength(0));
    await waitFor(() => expect(result.current.debate?.id).toBe("debate-B"));
  });

  it("PS157 B: stale fallback poll cannot hydrate or reschedule for the previous run", async () => {
    vi.useFakeTimers();
    try {
      // SSE closed → polling fallback engages
      sseHarness.status = "closed";

      let resolveStuckA: (v: unknown) => void;
      const stuckA = new Promise((resolve) => { resolveStuckA = resolve; });
      mockGetDebate
        .mockResolvedValue({ id: "debate-B", status: "running" }) // default after one-shots
        .mockResolvedValueOnce({ id: "debate-A", status: "running" }) // initial hydrate(A)
        .mockImplementationOnce(() => stuckA); // poll hydrate(A) — stays in-flight
      mockGetDebateResponses.mockResolvedValue({ items: [] });

      const { result, rerender } = renderHook(
        ({ id }) => useRunWorkspace(id),
        { initialProps: { id: "debate-A" } },
      );
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(result.current.debate?.id).toBe("debate-A");

      // Fire the first fallback poll → hydrate(A) starts and gets stuck in-flight
      await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
      expect(mockGetDebate.mock.calls.filter((c) => c[0] === "debate-A")).toHaveLength(2);

      // Navigate to B while A's poll is still in-flight
      rerender({ id: "debate-B" });
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(result.current.debate?.id).toBe("debate-B");

      // Resolve A's stuck poll — it is stale and must not reschedule itself
      await act(async () => {
        resolveStuckA!({ id: "debate-A", status: "running" });
        await vi.advanceTimersByTimeAsync(0);
      });

      // Advance well past several poll intervals: no further fetches for A,
      // and B's state is never clobbered by the stale loop.
      const aCallsBefore = mockGetDebate.mock.calls.filter((c) => c[0] === "debate-A").length;
      await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
      const aCallsAfter = mockGetDebate.mock.calls.filter((c) => c[0] === "debate-A").length;
      expect(aCallsAfter).toBe(aCallsBefore);
      expect(result.current.debate?.id).toBe("debate-B");
    } finally {
      vi.useRealTimers();
    }
  });

  it("PS157 B: navigating away from a terminal run resets connection state", async () => {
    mockGetDebate
      .mockResolvedValueOnce({ id: "debate-A", status: "completed" })
      .mockResolvedValueOnce({ id: "debate-B", status: "running" });
    mockGetDebateResponses.mockResolvedValue({ items: [] });

    const { result, rerender } = renderHook(
      ({ id }) => useRunWorkspace(id),
      { initialProps: { id: "debate-A" } },
    );
    await waitFor(() => expect(result.current.debate?.id).toBe("debate-A"));
    expect(result.current.status).toBe("completed");

    rerender({ id: "debate-B" });

    // The terminal state of A must not persist into B's hydration
    expect(result.current.coreState).toBe("loading");
    expect(result.current.status).toBe("loading");

    await waitFor(() => expect(result.current.debate?.id).toBe("debate-B"));
    expect(result.current.status).not.toBe("completed");
  });
});
