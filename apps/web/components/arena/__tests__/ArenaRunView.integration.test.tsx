import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { DebateDetail, PersistedModelResponse } from "@/lib/api/types";

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

// We specifically DO NOT mock SynthesisReveal or DecisionReportView here
// to test the integration between ArenaRunView and the actual report components.

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

describe("ArenaRunView Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the actual DecisionReportView for a completed public Arena run with no final_meta", () => {
    // Top-level synthesis report (as it would be provided by serialize_debate_public)
    const debate = makeDebate({
      status: "completed",
      models: [
        { model_id: "model-0", display_name: "GPT-4o", provider: "openai" },
        { model_id: "model-1", display_name: "Claude", provider: "anthropic" },
      ],
      synthesis_report: {
        title: "Integration Test Report",
        verdict: {
          decision_type: "consensus",
          confidence: 0.95,
          rationale: "They all agree on integration testing.",
        },
        executive_summary: "This is a full integration test.",
      },
      // final_meta is empty/undefined as in a public run without detailed internal meta
      final_meta: undefined,
    });
    
    const responses = makeResponses(2);
    
    render(
      <ArenaRunView
        debate={debate}
        events={[]}
        responses={responses}
        isTerminal={true}
        responsesState="ready"
      />
    );

    // At first, the report is hidden behind the reveal cover
    expect(screen.getByText("Final Verdict Synthesized")).toBeInTheDocument();
    
    // Click the reveal button
    const revealButton = screen.getByRole("button", { name: /View Verdict & Report/i });
    fireEvent.click(revealButton);

    // Now verify SynthesisReveal and its children are actually rendered
    // The SynthesisReveal header should show the decision type and confidence
    expect(screen.getByText("Integration Test Report")).toBeInTheDocument();
    
    // The DecisionReportView should render the executive summary and rationale
    expect(screen.getAllByText("This is a full integration test.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("They all agree on integration testing.").length).toBeGreaterThan(0);
    
    // Ensure ModelCards are also correctly rendered based on the responses
    const cards = screen.getAllByTestId("model-card");
    expect(cards.length).toBeGreaterThanOrEqual(2);
  });
});
