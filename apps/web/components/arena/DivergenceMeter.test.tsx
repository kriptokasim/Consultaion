import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { DivergenceMeter } from "./DivergenceMeter";
import { SynthesisReveal } from "./SynthesisReveal";

// Mock apiRequest
const mockApiRequest = vi.fn();
vi.mock("@/lib/apiClient", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
}));

describe("Arena Experience Enhancements", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  describe("DivergenceMeter Component", () => {
    const mockReport = {
      id: "report-id",
      debate_id: "test-debate",
      divergence_score: 0.4,
      consensus_claims: {
        claims: [
          { claim: "Consensus Point A", models: ["GPT-4o", "Claude"] },
        ],
      },
      contested_claims: {
        claims: [
          { claim: "Contested Point B", model: "Gemini" },
        ],
      },
      ready: true,
    };

    it("does not render divergence meter if debate is not completed", () => {
      render(<DivergenceMeter debateId="test-debate" isCompleted={false} />);
      expect(screen.getByText("Divergence Analysis Pending")).toBeInTheDocument();
    });

    it("fetches and renders divergence report if debate is completed", async () => {
      mockApiRequest.mockResolvedValueOnce(mockReport);
      render(<DivergenceMeter debateId="test-debate" isCompleted={true} />);

      await waitFor(() => {
        expect(screen.getByText("Claims Divergence Meter")).toBeInTheDocument();
      });

      expect(screen.getByText("Consensus Point A")).toBeInTheDocument();
      expect(screen.getByText("Contested Point B")).toBeInTheDocument();
      expect(screen.getByText("40% DIVIDED")).toBeInTheDocument();
    });

    it("allows user to cast a vote on consensus claim", async () => {
      mockApiRequest.mockResolvedValueOnce(mockReport);
      mockApiRequest.mockResolvedValueOnce({ success: true });

      render(<DivergenceMeter debateId="test-debate" isCompleted={true} />);

      await waitFor(() => {
        expect(screen.getByText("Consensus Point A")).toBeInTheDocument();
      });

      const voteButtons = screen.getAllByRole("button", { name: /Agree/i });
      expect(voteButtons.length).toBe(2); // One for Consensus, one for Contested

      fireEvent.click(voteButtons[0]);

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith({
          path: "/arena/test-debate/user-vote",
          method: "POST",
          body: {
            claim_text: "Consensus Point A",
            model_name: "GPT-4o",
            is_consensus: true,
          },
        });
      });
    });
  });

  describe("SynthesisReveal Component", () => {
    const mockResponses = [
      {
        model_id: "gpt-4",
        display_name: "GPT-4o",
        provider: "openai",
        content: "Response A",
        success: true,
      },
      {
        model_id: "gemini",
        display_name: "Gemini Pro",
        provider: "gemini",
        content: "Response B",
        success: true,
      },
    ];

    it("renders cover card before synthesis is revealed", () => {
      render(
        <SynthesisReveal
          synthesis="Final synthesized verdict."
          modelResponses={mockResponses}
          isSynthesisFailed={false}
          debateId="test-debate"
        />
      );

      expect(screen.getByText("Final Verdict Synthesized")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Reveal Final Verdict/i })).toBeInTheDocument();
      expect(screen.queryByText("Final synthesized verdict.")).not.toBeInTheDocument();
    });

    it("reveals final verdict and displays feedback buttons upon reveal", async () => {
      render(
        <SynthesisReveal
          synthesis="Final synthesized verdict."
          modelResponses={mockResponses}
          isSynthesisFailed={false}
          debateId="test-debate"
        />
      );

      const revealButton = screen.getByRole("button", { name: /Reveal Final Verdict/i });
      fireEvent.click(revealButton);

      expect(screen.getAllByText("Final synthesized verdict.").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("How would you rate this synthesis?")).toBeInTheDocument();

      const feedbackButton = screen.getByRole("button", { name: "Perfectly Combined" });
      fireEvent.click(feedbackButton);

      await waitFor(() => {
        expect(screen.getByText(/Thank you for your feedback!/i)).toBeInTheDocument();
      });
    });
  });
});
