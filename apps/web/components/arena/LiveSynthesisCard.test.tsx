import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SynthesisStreamingState } from "@/lib/workspace/synthesisReducer";
import { LiveSynthesisCard } from "./LiveSynthesisCard";

vi.mock("@/lib/i18n/client", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (!params) return key;
      return `${key}:${params.successful}/${params.total}`;
    },
  }),
}));

vi.mock("@/components/report/DecisionReportView", () => ({
  DecisionReportView: ({ rawSynthesis }: { rawSynthesis: string }) => (
    <div data-testid="decision-report">{rawSynthesis}</div>
  ),
}));

const baseState: SynthesisStreamingState = {
  synthesisId: "synth-1",
  runAttempt: 2,
  revision: 0,
  status: "provisional",
  text: "A visible provisional decision",
  report: null,
  responseIds: ["response-a"],
  successfulCount: 1,
  totalCount: 2,
  lastDeltaSequence: 0,
  provisionalPromoted: false,
  verificationStatus: "unavailable",
  isVerified: false,
  pipelineType: "structured",
  reportVersion: 1,
};

describe("LiveSynthesisCard", () => {
  it("shows a mobile-safe provisional decision with an accessible status", () => {
    render(<LiveSynthesisCard state={baseState} />);

    const card = screen.getByTestId("live-synthesis-card");
    expect(card).toHaveClass("min-w-0", "overflow-hidden");
    expect(screen.getByText("A visible provisional decision")).toBeVisible();
    expect(screen.getByText("arena.synthesis.draft:1/2")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("updates the same card to the final report", () => {
    const { rerender } = render(<LiveSynthesisCard state={baseState} />);
    const card = screen.getByTestId("live-synthesis-card");

    rerender(
      <LiveSynthesisCard
        state={{
          ...baseState,
          revision: 1,
          status: "final",
          text: "Converged final decision",
          report: { title: "Final" },
          responseIds: ["response-a", "response-b"],
          successfulCount: 2,
        }}
      />,
    );

    expect(screen.getByTestId("live-synthesis-card")).toBe(card);
    expect(screen.getByTestId("decision-report")).toHaveTextContent(
      "Converged final decision",
    );
    expect(screen.getByText("arena.synthesis.final:2/2")).toBeVisible();
  });
});
