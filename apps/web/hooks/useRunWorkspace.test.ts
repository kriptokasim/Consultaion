import { renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useRunWorkspace } from "./useRunWorkspace";

vi.mock("@/lib/api", () => ({
  getDebate: vi.fn().mockResolvedValue({ id: "mock", status: "perspectives_ready" }),
  continueDebate: vi.fn().mockResolvedValue({ id: "cont-1", status: "dispatched" }),
  retryDebate: vi.fn().mockResolvedValue({ id: "cont-1", status: "dispatched" }),
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) }),
}));

vi.mock("@/lib/config/runtime", () => ({
  API_ORIGIN: "http://localhost:8000",
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: vi.fn(() => ({ status: "idle" })),
}));

vi.mock("@/lib/api/normalizeEvent", () => ({
  normalizeEvent: vi.fn((e) => e),
}));

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
});
