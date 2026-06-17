import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { DebateDetail, DebateEvent, PersistedModelResponse } from "@/lib/api/types";
import type { ResponsesState } from "@/hooks/useRunWorkspace";

vi.mock("@/lib/apiClient", () => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) }),
}));

vi.mock("@/hooks/useCardKeyboardNav", () => ({
  useCardKeyboardNav: () => ({ containerRef: { current: null } }),
}));

vi.mock("@/components/debate/ShareRunButton", () => ({
  ShareRunButton: () => null,
}));

vi.mock("@/components/arena/CTABanner", () => ({
  PublicRunCTATop: () => null,
  PublicRunCTAFooter: () => null,
}));

vi.mock("@/components/arena/DivergenceMeter", () => ({
  DivergenceMeter: () => null,
}));

vi.mock("@/components/arena/SynthesisReveal", () => ({
  SynthesisReveal: () => null,
  SynthesisLoading: () => null,
}));

vi.mock("@/components/arena/ModelCard", () => ({
  ModelCard: ({ resp }: any) => (
    <div data-testid="model-card">{resp.display_name}</div>
  ),
  StreamingModelCard: () => <div data-testid="streaming-card" />,
  ModelLogo: () => null,
  SkeletonCard: ({ index }: any) => (
    <div data-testid={`skeleton-card-${index}`} className="skeleton" />
  ),
  getColors: () => ({
    bg: "", border: "", text: "", accent: "", glow: "",
  }),
}));

import ArenaRunView from "../ArenaRunView";

function makeDebate(overrides: Partial<DebateDetail> = {}): DebateDetail {
  return {
    id: "test-debate-id",
    prompt: "What is the meaning of life?",
    status: "completed",
    mode: "arena",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    config: {},
    ...overrides,
  } as DebateDetail;
}

function makeResponses(count: number): PersistedModelResponse[] {
  const providers = ["openai", "anthropic", "gemini", "meta"];
  const names = ["GPT-4o", "Claude", "Gemini", "Llama"];
  return Array.from({ length: count }, (_, i) => ({
    id: `${i + 1}`,
    debate_id: "test-debate-id",
    response_type: "arena_response",
    role: "arena_response",
    round: 1,
    model_id: `model-${i}`,
    display_name: names[i] || `Model ${i}`,
    provider: providers[i] || "unknown",
    content: `Response content from ${names[i] || "unknown"}`,
    success: true,
    error_code: null,
    error_message: null,
    retryable: false,
    created_at: "2025-01-01T00:00:00Z",
    metadata: {
      logo_url: null,
      persona_type: null,
      persona_tagline: null,
      attempt_count: 1,
    },
  }));
}

describe("ArenaRunView — FH121 regression tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("test_terminal_empty_shows_explicit_message", () => {
    const debate = makeDebate({
      status: "completed",
      final_meta: {},
    });
    render(
      <ArenaRunView
        debate={debate}
        events={[]}
        responses={[]}
        isTerminal={true}
        responsesState="empty"
      />
    );

    expect(
      screen.getByText(/no persisted model responses/i)
    ).toBeInTheDocument();
  });

  it("test_terminal_failed_shows_error_state", () => {
    const debate = makeDebate({
      status: "failed",
      final_meta: {},
    });
    render(
      <ArenaRunView
        debate={debate}
        events={[]}
        responses={[]}
        isTerminal={true}
        responsesState="failed"
        responsesError="fetch failed"
      />
    );

    expect(
      screen.getByText(/could not be retrieved/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /retry loading responses/i })
    ).toBeInTheDocument();
  });

  it("test_non_terminal_loading_shows_skeletons", () => {
    const debate = makeDebate({
      status: "running",
      final_meta: {},
    });
    render(
      <ArenaRunView
        debate={debate}
        events={[]}
        responses={[]}
        isTerminal={false}
        responsesState="loading"
      />
    );

    const skeletons = screen.getAllByTestId(/^skeleton-card-/);
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("test_completed_with_responses_shows_cards", () => {
    const debate = makeDebate({
      status: "completed",
      final_meta: {},
    });
    const responses = makeResponses(4);
    render(
      <ArenaRunView
        debate={debate}
        events={[]}
        responses={responses}
        isTerminal={true}
        responsesState="ready"
      />
    );

    const cards = screen.getAllByTestId("model-card");
    expect(cards.length).toBeGreaterThanOrEqual(4);
    expect(screen.getAllByText("GPT-4o").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Claude").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Gemini").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Llama").length).toBeGreaterThanOrEqual(1);
  });
});
