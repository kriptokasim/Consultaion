import { renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fetchWithAuth } from "@/lib/auth";
import { requestWithTimeout } from "@/lib/api";
import { useRunWorkspace } from "./useRunWorkspace";

vi.mock("@/lib/api", () => ({
  getDebate: vi.fn().mockResolvedValue({ id: "mock", status: "perspectives_ready" }),
  continueDebate: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  retryDebate: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  resolveContinuationByKey: vi.fn().mockResolvedValue({ continuation_id: "cont-1", status: "dispatched" }),
  requestWithTimeout: vi.fn().mockResolvedValue([]),
  extractEventItems: vi.fn((data: unknown) => Array.isArray(data) ? data : []),
  TimeoutError: class TimeoutError extends Error { name = "TimeoutError" },
  REQUEST_TIMEOUT: "REQUEST_TIMEOUT",
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: "dispatched", continuation_id: "cont-1" }) }),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: vi.fn(() => ({ status: "idle" })),
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
    expect(result.current.debate.id).toBe("mock"); // Debate data should still be there
  });
});
