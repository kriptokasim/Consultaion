import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { PipelineProgress, derivePipelineStage } from "./PipelineProgress";

describe("PipelineProgress", () => {
  describe("derivePipelineStage", () => {
    it("returns queued for queued debates", () => {
      const debate = { status: "queued" };
      expect(derivePipelineStage(debate, new Set())).toBe("queued");
    });

    it("returns complete for completed debates", () => {
      const debate = { status: "completed" };
      expect(derivePipelineStage(debate, new Set())).toBe("complete");
      expect(derivePipelineStage({ status: "success" }, new Set())).toBe("complete");
      expect(derivePipelineStage({ status: "completed_budget" }, new Set())).toBe("complete");
    });

    it("returns queued for failed debates", () => {
      const debate = { status: "failed" };
      expect(derivePipelineStage(debate, new Set())).toBe("queued");
    });

    it("returns collecting_responses for partial responses", () => {
      const debate = {
        status: "running",
        config: { models: ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "llama-3"] },
      };
      // 2 responses out of 4 expected
      const eventTypes = new Set(["arena_started", "arena_response"]);
      const liveResponseCount = 2;
      expect(derivePipelineStage(debate, eventTypes, liveResponseCount)).toBe("collecting_responses");
    });

    it("returns scoring for all expected responses", () => {
      const debate = {
        status: "running",
        config: { models: ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "llama-3"] },
      };
      // 4 responses out of 4 expected
      const eventTypes = new Set(["arena_started", "arena_response"]);
      const liveResponseCount = 4;
      expect(derivePipelineStage(debate, eventTypes, liveResponseCount)).toBe("scoring");
    });

    it("counts message/seat_message/model_response events", () => {
      // Test event filtering
      const debate = {
        status: "running",
        config: { models: ["gpt-4o", "claude-3"] },
      };
      const eventTypes = new Set(["message"]);
      // 1 response
      expect(derivePipelineStage(debate, eventTypes, 1)).toBe("collecting_responses");
      // 2 responses
      expect(derivePipelineStage(debate, eventTypes, 2)).toBe("scoring");
    });

    it("returns verifying when synthesis and quality_meta exist", () => {
      const debate = {
        status: "running",
        synthesis_report: {
          quality_meta: {
            renderable: true,
          },
        },
      };
      const eventTypes = new Set(["arena_synthesis"]);
      expect(derivePipelineStage(debate, eventTypes)).toBe("verifying");
    });

    it("returns synthesizing when synthesis exists but quality_meta does not", () => {
      const debate = {
        status: "running",
        synthesis_report: {},
      };
      const eventTypes = new Set(["arena_synthesis"]);
      expect(derivePipelineStage(debate, eventTypes)).toBe("synthesizing");
    });
  });

  describe("PipelineProgress Component Rendering", () => {
    it("renders the pipeline progress title", () => {
      render(<PipelineProgress currentStage="collecting_responses" />);
      expect(screen.getByText("Pipeline Progress")).toBeInTheDocument();
    });

    it("renders the elapsed time notice and advice", () => {
      render(<PipelineProgress currentStage="collecting_responses" elapsedSeconds={60} />);
      expect(screen.getByText(/Still working. Some providers are taking longer than usual/)).toBeInTheDocument();
    });

    it("renders active stage in amber/orange highlighting", () => {
      render(
        <PipelineProgress
          currentStage="collecting_responses"
          responsesReceived={2}
          modelsExpected={4}
        />
      );
      expect(screen.getByText("Collecting model responses (2/4 received)")).toBeInTheDocument();
    });

    it("renders evaluating responses count when in scoring stage", () => {
      render(
        <PipelineProgress
          currentStage="scoring"
          responsesReceived={4}
          modelsExpected={4}
          scoresReceived={3}
        />
      );
      expect(screen.getByText("Evaluating responses (3/4 scored)")).toBeInTheDocument();
    });
  });
});
