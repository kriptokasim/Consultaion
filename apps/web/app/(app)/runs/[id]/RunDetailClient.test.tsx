import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import React from "react";
import RunDetailClient from "./RunDetailClient";
import { useDebate } from "@/lib/api/hooks/useDebate";
import { fetchWithAuth } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "test-run-id" }),
}));

vi.mock("@/lib/api/hooks/useDebate", () => ({
  useDebate: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock("@/components/debate/DebateArena", () => ({
  default: () => <div data-testid="debate-arena" />,
}));

vi.mock("@/components/arena/ArenaRunView", () => ({
  default: () => <div data-testid="arena-run-view" />,
}));

vi.mock("@/lib/sse", () => ({
  useEventSource: () => ({
    lastEvent: null,
    status: "connected",
  }),
}));

describe("RunDetailClient Hydration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hydrates from /timeline on mount", async () => {
    const mockRefetch = vi.fn();
    (useDebate as any).mockReturnValue({
      data: { id: "test-run-id", status: "running", mode: "arena", created_at: new Date().toISOString() },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    const mockTimelineEvents = [
      { id: "e1", type: "arena_started", ts: new Date().toISOString() }
    ];

    (fetchWithAuth as any).mockImplementation((url: string) => {
      if (url.includes("/me")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ email: "test@example.com" }) });
      }
      if (url.includes("/timeline")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTimelineEvents),
        });
      }
      return Promise.resolve({ ok: false });
    });

    render(<RunDetailClient />);

    await waitFor(() => {
      expect(fetchWithAuth).toHaveBeenCalledWith("/debates/test-run-id/timeline");
    });
  });

  it("falls back to /events if /timeline fails", async () => {
    const mockRefetch = vi.fn();
    (useDebate as any).mockReturnValue({
      data: { id: "test-run-id", status: "running", mode: "arena", created_at: new Date().toISOString() },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    const mockFallbackEvents = [
      { id: "e1", type: "arena_response", ts: new Date().toISOString(), payload: { text: "hello" } }
    ];

    (fetchWithAuth as any).mockImplementation((url: string) => {
      if (url.includes("/me")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ email: "test@example.com" }) });
      }
      if (url.includes("/timeline")) {
        return Promise.resolve({
          ok: false,
          status: 500,
        });
      }
      if (url.includes("/events")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ items: mockFallbackEvents }),
        });
      }
      return Promise.resolve({ ok: false });
    });

    render(<RunDetailClient />);

    await waitFor(() => {
      expect(fetchWithAuth).toHaveBeenCalledWith("/debates/test-run-id/timeline");
      expect(fetchWithAuth).toHaveBeenCalledWith("/debates/test-run-id/events");
    });
  });
});
