import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ShareRunButton } from "./ShareRunButton";
import React from "react";

const mockPushToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ pushToast: mockPushToast }),
}));

const mockFetchWithAuth = vi.fn();
vi.mock("@/lib/auth", () => ({
  fetchWithAuth: (...args: any[]) => mockFetchWithAuth(...args),
}));

const mockTrackEvent = vi.fn();
vi.mock("@/lib/analytics", () => ({
  trackEvent: (...args: any[]) => mockTrackEvent(...args),
}));

describe("ShareRunButton Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
    });
    window.history.replaceState({}, "", "/run/test-id");
  });

  it("renders share button in private state", () => {
    render(<ShareRunButton debateId="test-id" initiallyPublic={false} />);
    expect(screen.getByRole("button", { name: "Share" })).toBeInTheDocument();
  });

  it("renders share button in public state", () => {
    render(<ShareRunButton debateId="test-id" initiallyPublic={true} />);
    expect(screen.getByRole("button", { name: "Public link" })).toBeInTheDocument();
  });

  it("copies a referral-aware public link when sharing", async () => {
    mockFetchWithAuth.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        id: "test-id",
        is_public: true,
        referral_token: "ref-token-123",
      }),
    });

    render(<ShareRunButton debateId="test-id" initiallyPublic={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    expect(screen.getByText("Make this run public?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Make public and copy link" }));

    await waitFor(() => {
      expect(mockFetchWithAuth).toHaveBeenCalledWith("/debates/test-id/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_public: true }),
      });
    });

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    });
    const copied = vi.mocked(navigator.clipboard.writeText).mock.calls[0][0] as string;
    const copiedUrl = new URL(copied);
    expect(copiedUrl.pathname).toBe("/run/test-id");
    expect(copiedUrl.searchParams.get("ref")).toBe("ref-token-123");

    expect(mockPushToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Link copied!" })
    );
    expect(mockTrackEvent).toHaveBeenCalledWith(
      "arena_share_enabled",
      expect.objectContaining({ debate_id: "test-id" })
    );
    // The raw referral token is intentionally absent from analytics payloads.
    expect(mockTrackEvent).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ referral_token: "ref-token-123" })
    );
  });

  it("mints a fresh referral token when copying an already-public run", async () => {
    mockFetchWithAuth.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        id: "test-id",
        is_public: true,
        referral_token: "fresh-token",
      }),
    });

    render(<ShareRunButton debateId="test-id" initiallyPublic />);
    fireEvent.click(screen.getByRole("button", { name: "Public link" }));
    fireEvent.click(screen.getByRole("button", { name: "Copy public link" }));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = vi.mocked(navigator.clipboard.writeText).mock.calls[0][0] as string;
    expect(new URL(copied).searchParams.get("ref")).toBe("fresh-token");
  });
});
