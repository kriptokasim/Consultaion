import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fetchWithAuth } from "@/lib/auth";
import { requestWithTimeout, getDebate, getDebateResponses } from "@/lib/api";
import { useRunWorkspace } from "./useRunWorkspace";

vi.mock("@/lib/api", () => ({
  getDebate: vi.fn().mockResolvedValue({ id: "mock", status: "perspectives_ready" }),
  getDebateResponses: vi.fn().mockResolvedValue({ items: [] }),
  continueDebate: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  retryDebate: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  resolveContinuationByKey: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  requestWithTimeout: vi.fn().mockResolvedValue([]),
  extractEventItems: vi.fn((data: unknown) => Array.isArray(data) ? data : []),
  TimeoutError: class TimeoutError extends Error { name = "TimeoutError" },
  ApiError: class ApiError extends Error { status = 500 },
  REQUEST_TIMEOUT: "REQUEST_TIMEOUT",
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: "dispatched", continuation_id: "cont-1" }) }),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: vi.fn((url, options: any) => {
    // If the test has set a global mock handler, call it so tests can access onEvent
    if ((globalThis as any).__mockUseEventSourceCallback) {
      (globalThis as any).__mockUseEventSourceCallback(url, options);
    }
    return { status: (globalThis as any).__mockSseStatus || "idle" };
  }),
}));

vi.mock("@/lib/api/normalizeEvent", () => {
  return {
    normalizeEvent: vi.fn((e) => e),
    normalizeTimelineItems: vi.fn((items) => items),
  };
});

vi.mock("@/lib/timeline/types", () => ({}));

const STORAGE_KEY_PREFIX = "consultaion:continuation";

function getStorageKey(debateId: string): string {
  return `${STORAGE_KEY_PREFIX}:${debateId}`;
}

function setStoredIntent(debateId: string, intent: any) {
  localStorage.setItem(getStorageKey(debateId), JSON.stringify(intent));
}

function getStoredIntent(debateId: string) {
  const raw = localStorage.getItem(getStorageKey(debateId));
  return raw ? JSON.parse(raw) : null;
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("useRunWorkspace -- localStorage persistence", () => {
  it("restores isContinuing on page load when intent has phase=server_acknowledged", () => {
    const debateId = "test-debate-2";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-2",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "server_acknowledged",
      continuationId: "cont-123",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(true);
    expect(result.current.outcomeUnknown).toBe(true);
  });

  it("restores isContinuing on page load when intent has phase=request_sent", () => {
    const debateId = "test-debate-3";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-3",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "request_sent",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(true);
    expect(result.current.outcomeUnknown).toBe(true);
  });

  it("does not restore expired intent", () => {
    const debateId = "test-debate-4";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-4",
      createdAt: new Date(Date.now() - 86400000 * 2).toISOString(),
      updatedAt: new Date(Date.now() - 86400000 * 2).toISOString(),
      phase: "tracking",
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(false);
    expect(getStoredIntent(debateId)).toBeNull();
  });

  it("shows outcomeUnknown=true when page refreshes after successful POST", () => {
    const debateId = "test-debate-9";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-9",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "server_acknowledged",
      continuationId: "cont-9",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.outcomeUnknown).toBe(true);
  });

  it("intent_created phase restores isContinuing but not outcomeUnknown", () => {
    const debateId = "test-debate-11";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-11",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "intent_created",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(true);
  });

  it("tracking phase restores isContinuing and outcomeUnknown", () => {
    const debateId = "test-debate-12";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-12",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "tracking",
      continuationId: "cont-12",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(true);
    expect(result.current.outcomeUnknown).toBe(true);
  });

  it("no intent means not continuing", () => {
    const debateId = "test-debate-13";
    const { result } = renderHook(() => useRunWorkspace(debateId));
    expect(result.current.isContinuing).toBe(false);
    expect(result.current.outcomeUnknown).toBe(false);
  });

  it("cleans up intent on mount if continuation has failed on the server", async () => {
    const debateId = "test-debate-failed-recovery";
    setStoredIntent(debateId, {
      debateId,
      idempotencyKey: "key-failed",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      phase: "tracking",
      continuationId: "cont-failed",
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    vi.mocked(fetchWithAuth).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "failed", continuation_id: "cont-failed" })
    } as any);

    const { result } = renderHook(() => useRunWorkspace(debateId));
    await vi.waitFor(() => {
      expect(result.current.isContinuing).toBe(false);
    });
    expect(getStoredIntent(debateId)).toBeNull();
  });
});

describe("useRunWorkspace -- timeline and fallback events", () => {
  it("uses /events fallback when /timeline fails, and returns normalized events", async () => {
    const debateId = "test-fallback-debate";
    
    // First call is /timeline (fails), Second is /events (succeeds)
    vi.mocked(requestWithTimeout)
      .mockRejectedValueOnce(new Error("Timeline fetch failed"))
      .mockResolvedValueOnce([
        { id: "event-1", type: "message", ts: "2026-06-16T12:00:00Z", payload: { text: "Hello" } }
      ]);
      
    const { result } = renderHook(() => useRunWorkspace(debateId));
    
    await vi.waitFor(() => {
      expect(result.current.status).not.toBe("loading");
    });
    
    expect(result.current.hydrationQuality).toBe("events_fallback");
    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].id).toBe("event-1");
  });

  it("handles when both /timeline and /events fail, preserving debate context", async () => {
    const debateId = "test-both-fail-debate";
    
    vi.mocked(requestWithTimeout)
      .mockRejectedValueOnce(new Error("Timeline fetch failed"))
      .mockRejectedValueOnce(new Error("Events fetch failed"));
      
    const { result } = renderHook(() => useRunWorkspace(debateId));
    
    await vi.waitFor(() => {
      expect(result.current.status).not.toBe("loading");
    });
    
    expect(result.current.hydrationQuality).toBe("debate_only");
    expect(result.current.events.length).toBe(0);
    expect(result.current.timelineError).toBe("Timeline fetch failed");
    expect(result.current.eventsError).toBe("Events fetch failed");
    expect(result.current.debate?.id).toBe("mock"); // Debate data should still be there
  });
});

describe("useRunWorkspace -- persisted response refresh", () => {
  it("serializes terminal-event refreshes and performs one trailing refresh", async () => {
    let handleEvent: ((event: any) => void) | undefined;
    (globalThis as any).__mockUseEventSourceCallback = (_url: unknown, options: any) => {
      handleEvent = options?.onEvent;
    };

    const { result } = renderHook(() => useRunWorkspace("refresh-debate"));
    await vi.waitFor(() => expect(result.current.coreState).toBe("ready"));
    const baselineCalls = vi.mocked(getDebateResponses).mock.calls.length;

    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    let activeRequests = 0;
    let maxActiveRequests = 0;
    vi.mocked(getDebateResponses).mockImplementation(async () => {
      activeRequests += 1;
      maxActiveRequests = Math.max(maxActiveRequests, activeRequests);
      await gate;
      activeRequests -= 1;
      return { items: [] } as any;
    });

    act(() => {
      handleEvent?.({
        type: "model_response_completed",
        payload: { response_id: "response-1", model_id: "model-1" },
      });
      handleEvent?.({
        type: "model_response_completed",
        payload: { response_id: "response-2", model_id: "model-2" },
      });
    });

    await vi.waitFor(() => expect(activeRequests).toBe(1));
    expect(maxActiveRequests).toBe(1);

    await act(async () => {
      release?.();
      await gate;
    });
    await vi.waitFor(() => {
      expect(vi.mocked(getDebateResponses).mock.calls.length).toBe(baselineCalls + 2);
    });
    expect(maxActiveRequests).toBe(1);

    delete (globalThis as any).__mockUseEventSourceCallback;
  });
});

describe("useRunWorkspace -- SSE watchdog and terminal handling", () => {
  let mockHandleEvent: any;

  beforeEach(() => {
    vi.useFakeTimers();
    (globalThis as any).__mockSseStatus = "connected";
    (globalThis as any).__mockUseEventSourceCallback = (url: any, options: any) => {
      mockHandleEvent = options?.onEvent;
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete (globalThis as any).__mockSseStatus;
    delete (globalThis as any).__mockUseEventSourceCallback;
  });

  it("keeps model response transport events out of the timeline and batches deltas per frame", () => {
    let frameCallback: FrameRequestCallback | null = null;
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      frameCallback = callback;
      return 1;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn(() => {
      frameCallback = null;
    }));
    const { result } = renderHook(() => useRunWorkspace("test-debate"));

    act(() => {
      mockHandleEvent({
        id: "stream-queued-1",
        type: "model_response_queued",
        payload: {
          response_id: "response-1",
          model_id: "model-1",
          display_name: "Model 1",
        },
      });
      mockHandleEvent({
        id: "stream-delta-1",
        type: "model_response_delta",
        payload: {
          response_id: "response-1",
          model_id: "model-1",
          text: "Hello",
          delta_sequence: 1,
          accumulated_chars: 5,
        },
      });
      mockHandleEvent({
        id: "stream-delta-2",
        type: "model_response_delta",
        payload: {
          response_id: "response-1",
          model_id: "model-1",
          text: " world",
          delta_sequence: 2,
          accumulated_chars: 11,
        },
      });
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.streamingState.buffers.get("response-1")?.accumulatedText).toBe("");
    expect(requestAnimationFrame).toHaveBeenCalledTimes(1);

    act(() => frameCallback?.(16));

    expect(result.current.streamingState.buffers.get("response-1")?.accumulatedText).toBe("Hello world");
  });

  it("connected-but-silent SSE starts polling", async () => {
    const { result } = renderHook(() => useRunWorkspace("test-debate"));
    expect(result.current.isPollingFallback).toBe(false);
    
    // Advance past silence timeout (10000ms)
    act(() => {
      vi.advanceTimersByTime(11000);
    });
    expect(result.current.isSilent).toBe(true);
    expect(result.current.isPollingFallback).toBe(true);
  });

  it("incoming event stops polling", async () => {
    const { result } = renderHook(() => useRunWorkspace("test-debate"));
    
    // Silence starts polling
    act(() => {
      vi.advanceTimersByTime(11000);
    });
    expect(result.current.isPollingFallback).toBe(true);

    // Incoming event should reset silence and stop polling
    act(() => {
      mockHandleEvent({ type: "message", ts: new Date().toISOString() });
    });
    
    expect(result.current.isSilent).toBe(false);
    expect(result.current.isPollingFallback).toBe(false);
  });

  it("terminal run clears watchdog timers and polling", async () => {
    // Mock getDebate to return terminal status
    vi.mocked(getDebate).mockResolvedValueOnce({ id: "test", status: "completed" });
    
    const { result } = renderHook(() => useRunWorkspace("test-debate"));
    
    await vi.waitFor(() => {
      expect(result.current.debate?.status).toBe("completed");
    });

    // Advance time, shouldn't start polling because it's terminal
    act(() => {
      vi.advanceTimersByTime(11000);
    });
    
    expect(result.current.isPollingFallback).toBe(false);
    expect(result.current.isSilent).toBe(false);
  });
});
