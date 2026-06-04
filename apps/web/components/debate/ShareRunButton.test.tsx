import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ShareRunButton } from "./ShareRunButton";
import React from "react";

// Mock toast hook
const mockPushToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    pushToast: mockPushToast,
  }),
}));

// Mock auth module
const mockFetchWithAuth = vi.fn();
vi.mock("@/lib/auth", () => ({
  fetchWithAuth: (...args: any[]) => mockFetchWithAuth(...args),
}));

// Mock analytics
const mockTrackEvent = vi.fn();
vi.mock("@/lib/analytics", () => ({
  trackEvent: (...args: any[]) => mockTrackEvent(...args),
}));

describe("ShareRunButton Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock navigator.clipboard
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve()),
      },
      writable: true,
    });
    // Mock window.location
    Object.defineProperty(window, "location", {
      value: {
        href: "http://localhost/run/test-id",
      },
      writable: true,
    });
  });

  it("renders share button in private state", () => {
    render(<ShareRunButton debateId="test-id" initiallyPublic={false} />);
    expect(screen.getByRole("button", { name: "Share" })).toBeInTheDocument();
  });

  it("renders share button in public state", () => {
    render(<ShareRunButton debateId="test-id" initiallyPublic={true} />);
    expect(screen.getByRole("button", { name: "Public link" })).toBeInTheDocument();
  });

  it("opens modal dialog on trigger click and allows sharing public link", async () => {
    mockFetchWithAuth.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    render(<ShareRunButton debateId="test-id" initiallyPublic={false} />);
    
    // Open Dialog
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    
    expect(screen.getByText("Make this run public?")).toBeInTheDocument();

    const makePublicButton = screen.getByRole("button", {
      name: "Make public and copy link",
    });
    
    fireEvent.click(makePublicButton);

    await waitFor(() => {
      expect(mockFetchWithAuth).toHaveBeenCalledWith("/debates/test-id/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_public: true }),
      });
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("http://localhost/run/test-id");
    expect(mockPushToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Link copied!" })
    );
    expect(mockTrackEvent).toHaveBeenCalledWith(
      "arena_share_enabled",
      expect.objectContaining({ debate_id: "test-id" })
    );
  });
});
