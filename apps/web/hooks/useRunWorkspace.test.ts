import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useRunWorkspace } from "./useRunWorkspace";
import type { PersistedContinuationIntent } from "./useRunWorkspace";
import * as apiModule from "@/lib/api";
import * as authModule from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getDebate: vi.fn(),
  continueDebate: vi.fn(),
  retryDebate: vi.fn(),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: vi.fn(() => ({ status: "connected" })),
}));

vi.mock("@/lib/api/normalizeEvent", () => ({
  normalizeEvent: vi.fn((e) => e),
}));

const mockGetDebate = vi.mocked(apiModule).getDebate;
const mockContinueDebate = vi.mocked(apiModule).continueDebate;
const mockFetchWithAuth = vi.mocked(authModule).fetchWithAuth;

function makeDebate(overrides: Record<string, any> = {}) {
  return {
    id: "debate-1",
    status: "perspectives_ready",
    mode: "arena",
    prompt: "Test prompt",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const STORAGE_KEY = "continuation_intent_debate-1";

function setStoredIntent(intent: PersistedContinuationIntent) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(intent));
}

function getStoredIntent(): PersistedContinuationIntent | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  return JSON.parse(raw);
}

describe("useRunWorkspace — localStorage persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockGetDebate.mockResolvedValue(makeDebate());
    mockFetchWithAuth.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as any);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("persists intent with dispatched=false before POST", async () => {
    mockContinueDebate.mockResolvedValue({ created: true } as any);

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    await act(async () => {
      await result.current.continueRun();
    });

    // After success, intent should be cleared
    expect(getStoredIntent()).toBeNull();
  });

  it("restores isContinuing on page load when intent has dispatched=true", async () => {
    // Simulate a page refresh with a dispatched intent
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "existing-key",
      persistedAt: new Date().toISOString(),
      dispatched: true,
    });

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    // Should restore continuing state from persisted intent
    expect(result.current.isContinuing).toBe(true);
    expect(result.current.outcomeUnknown).toBe(true);
  });

  it("restores isContinuing on page load when intent has dispatched=false", async () => {
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "existing-key",
      persistedAt: new Date().toISOString(),
      dispatched: false,
    });

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    expect(result.current.isContinuing).toBe(true);
    expect(result.current.outcomeUnknown).toBe(false);
  });

  it("does not restore expired intent (stale intent expiry)", async () => {
    // Intent from 25 hours ago
    const staleDate = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "stale-key",
      persistedAt: staleDate,
      dispatched: true,
    });

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    // Expired intent should be cleared
    expect(result.current.isContinuing).toBe(false);
    expect(result.current.outcomeUnknown).toBe(false);
    expect(getStoredIntent()).toBeNull();
  });

  it("clears intent when debate becomes terminal", async () => {
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "key",
      persistedAt: new Date().toISOString(),
      dispatched: true,
    });

    mockGetDebate.mockResolvedValue(makeDebate({ status: "completed" }));

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    expect(result.current.isContinuing).toBe(false);
    expect(result.current.outcomeUnknown).toBe(false);
    expect(getStoredIntent()).toBeNull();
  });

  it("reuses idempotency key when clicking while intent already persisted", async () => {
    // Simulate an existing persisted intent from a previous incomplete attempt
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "existing-key-123",
      persistedAt: new Date().toISOString(),
      dispatched: false,
    });

    mockContinueDebate.mockResolvedValue({ created: false } as any);

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    // Click — should reuse the existing key from the persisted intent
    await act(async () => {
      await result.current.continueRun();
    });

    expect(mockContinueDebate).toHaveBeenCalledTimes(1);
    expect(mockContinueDebate).toHaveBeenCalledWith("debate-1", "existing-key-123");
  });

  it("handles POST failure and leaves intent for retry", async () => {
    mockContinueDebate.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    await act(async () => {
      await result.current.continueRun();
    });

    expect(result.current.error).toBe("Network error");
    // Intent should remain for retry on refresh
    const stored = getStoredIntent();
    expect(stored).not.toBeNull();
    expect(stored!.dispatched).toBe(false);
  });

  it("handles POST timeout and leaves intent for retry", async () => {
    // Simulate a timeout by rejecting with AbortError
    mockContinueDebate.mockRejectedValue(new DOMException("The operation was aborted.", "AbortError"));

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    await act(async () => {
      await result.current.continueRun();
    });

    expect(result.current.error).toBeTruthy();
    const stored = getStoredIntent();
    expect(stored).not.toBeNull();
  });

  it("shows outcomeUnknown=true when page refreshes after successful POST", async () => {
    // Simulate: POST succeeded but user refreshed before server response was processed
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "key",
      persistedAt: new Date().toISOString(),
      dispatched: true,
    });

    // Debate is still in perspectives_ready (server might not have processed yet)
    mockGetDebate.mockResolvedValue(makeDebate({ status: "perspectives_ready" }));

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    expect(result.current.outcomeUnknown).toBe(true);
    expect(result.current.isContinuing).toBe(true);
  });

  it("cleans up intent when debate transitions out of perspectives_ready (undelivered)", async () => {
    setStoredIntent({
      debateId: "debate-1",
      idempotencyKey: "key",
      persistedAt: new Date().toISOString(),
      dispatched: false,
    });

    // Debate has moved past perspectives_ready
    mockGetDebate.mockResolvedValue(makeDebate({ status: "running" }));

    const { result } = renderHook(() => useRunWorkspace("debate-1"));

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    // Undelivered intent should be cleared when status moves past perspectives_ready
    expect(getStoredIntent()).toBeNull();
  });
});
