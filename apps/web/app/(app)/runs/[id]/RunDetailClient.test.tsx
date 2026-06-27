import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import RunDetailClient, { resolveRunViewKind } from "./RunDetailClient";
import { useRunWorkspace } from "@/hooks/useRunWorkspace";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "test-run-id" }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/hooks/useRunWorkspace", () => ({
  useRunWorkspace: vi.fn(),
}));

// Enable feature flags for workspace tests
vi.mock("@/lib/feature-flags", () => ({
  isFeatureEnabled: (flag: string) => {
    if (flag === "unifiedWorkspace" || flag === "mobileWorkspaceV2" || flag === "stagedDecisionPipelinePublic") return true;
    return false;
  },
  featureFlags: {
    unifiedWorkspace: true,
    mobileWorkspaceV2: true,
    stagedDecisionPipelinePublic: true,
  },
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ email: "test@example.com" }),
  })),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock("@/components/debate/DebateArena", () => ({
  default: () => <div data-testid="debate-arena" />,
}));

vi.mock("@/components/arena/ArenaRunView", () => ({
  default: () => <div data-testid="arena-run-view" />,
}));

vi.mock("@/components/workspace", () => ({
  WorkspaceHeader: () => <div data-testid="workspace-header" />,
  DesktopStageRail: () => <div data-testid="desktop-stage-rail" />,
  MobileStageBar: () => <div data-testid="mobile-stage-bar" />,
  PerspectivesGrid: () => <div data-testid="perspectives-grid" />,
  PerspectivesReadyAction: () => <div data-testid="perspectives-ready-action" />,
}));

describe("RunDetailClient Hydration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading skeleton when workspace status is loading", async () => {
    (useRunWorkspace as any).mockReturnValue({
      debate: null,
      events: [],
      responses: [],
      status: "loading",
      sseStatus: "connected",
      error: null,
      continueRun: vi.fn(),
      isContinuing: false,
      refetch: vi.fn(),
      retryResponses: vi.fn(),
      hydrationQuality: "complete",
      timelineError: null,
      eventsError: null,
      responsesState: "idle",
      responsesError: null,
      timelineState: "idle",
      streamingState: { buffers: new Map() },
      mergedStreamingResponses: [],
      coreState: "loading",
      coreErrorCode: null,
      coreHttpStatus: null,
      outcomeUnknown: false,
      isPollingFallback: false,
    });

    const { container } = render(<RunDetailClient />);
    // Verify skeleton card divs exist
    expect(container.getElementsByClassName("animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders error alert when core state has a typed error", async () => {
    (useRunWorkspace as any).mockReturnValue({
      debate: null,
      events: [],
      responses: [],
      status: "error",
      sseStatus: "connected",
      error: "Server encountered an internal error",
      continueRun: vi.fn(),
      isContinuing: false,
      refetch: vi.fn(),
      retryResponses: vi.fn(),
      hydrationQuality: "failed",
      timelineError: null,
      eventsError: null,
      responsesState: "idle",
      responsesError: null,
      timelineState: "idle",
      streamingState: { buffers: new Map() },
      mergedStreamingResponses: [],
      coreState: "failed",
      coreErrorCode: "server_error",
      coreHttpStatus: 500,
      outcomeUnknown: false,
      isPollingFallback: false,
    });

    render(<RunDetailClient />);
    expect(screen.getByText("Server Error")).toBeInTheDocument();
    expect(screen.getByText("Server encountered an internal error")).toBeInTheDocument();
  });

  it("renders running workspace view when debate is active", async () => {
    (useRunWorkspace as any).mockReturnValue({
      debate: {
        id: "test-run-id",
        status: "running",
        mode: "arena",
        prompt: "Should we use Kafka?",
        created_at: new Date().toISOString(),
      },
      events: [
        { id: "e1", type: "arena_started", ts: new Date().toISOString() }
      ],
      responses: [],
      status: "streaming",
      sseStatus: "connected",
      error: null,
      continueRun: vi.fn(),
      isContinuing: false,
      refetch: vi.fn(),
      retryResponses: vi.fn(),
      hydrationQuality: "complete",
      timelineError: null,
      eventsError: null,
      responsesState: "idle",
      responsesError: null,
      timelineState: "idle",
      streamingState: { buffers: new Map() },
      mergedStreamingResponses: [],
      coreState: "ready",
      coreErrorCode: null,
      coreHttpStatus: null,
      outcomeUnknown: false,
      isPollingFallback: false,
    });

    render(<RunDetailClient />);
    expect(screen.getByTestId("workspace-header")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-stage-rail")).toBeInTheDocument();
  });
});

// ─── P143: resolveRunViewKind tests ─────────────────────────────────
describe("resolveRunViewKind — P143 mode fallback", () => {
  it("returns 'arena' for undefined mode", () => {
    expect(resolveRunViewKind(undefined)).toBe("arena");
  });

  it("returns 'arena' for null mode", () => {
    expect(resolveRunViewKind(null)).toBe("arena");
  });

  it("returns 'arena' for 'arena' mode", () => {
    expect(resolveRunViewKind("arena")).toBe("arena");
  });

  it("returns 'debate' for 'debate' mode", () => {
    expect(resolveRunViewKind("debate")).toBe("debate");
  });

  it("returns 'debate' for 'parliament' mode", () => {
    expect(resolveRunViewKind("parliament")).toBe("debate");
  });

  it("returns 'compare' for 'compare' mode", () => {
    expect(resolveRunViewKind("compare")).toBe("compare");
  });

  it("returns 'conversation' for 'conversation' mode", () => {
    expect(resolveRunViewKind("conversation")).toBe("conversation");
  });

  it("returns 'voting' for 'voting' mode", () => {
    expect(resolveRunViewKind("voting")).toBe("voting");
  });

  it("returns 'debate' for unknown mode string", () => {
    expect(resolveRunViewKind("something_unknown")).toBe("debate");
  });
});

