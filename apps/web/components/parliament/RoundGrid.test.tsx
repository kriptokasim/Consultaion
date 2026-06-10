import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import RoundGrid from "./RoundGrid";
import type { DebateEvent } from "./types";

describe("RoundGrid Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock IntersectionObserver for JSDOM testing
    class MockIntersectionObserver {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    }
    Object.defineProperty(window, "IntersectionObserver", {
      value: MockIntersectionObserver,
      writable: true,
      configurable: true,
    });

    // Mock scrollTo
    Object.defineProperty(window, "scrollTo", {
      value: vi.fn(),
      writable: true,
      configurable: true,
    });
  });

  it("renders empty fallback when there are no rounds", () => {
    render(<RoundGrid events={[]} />);
    expect(screen.getByText("No deliberation rounds have been recorded yet.")).toBeInTheDocument();
  });

  it("renders deliberation grid correctly with rounds and persona cards", () => {
    const mockEvents: DebateEvent[] = [
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Optimist response round 1",
        round: 1,
        provider: "openai/gpt-4o",
      } as any,
      {
        type: "message",
        actor: "Systems Architect",
        text: "Systems Architect response round 1",
        round: 1,
        role: "agent",
        provider: "anthropic/claude-3-5-sonnet",
      } as any,
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Optimist response round 2",
        round: 2,
        provider: "openai/gpt-4o",
      } as any,
    ];

    render(<RoundGrid events={mockEvents} />);

    // Check header
    expect(screen.getByText("Round 1 Deliberation")).toBeInTheDocument();
    expect(screen.getByText("Round 2 Deliberation")).toBeInTheDocument();

    // Check navigator
    expect(screen.getByText("Jump to Round:")).toBeInTheDocument();
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.getByText("R2")).toBeInTheDocument();

    // Check speech cards
    expect(screen.getAllByText("Optimist").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("OpenAI · GPT-4o").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Optimist response round 1")).toBeInTheDocument();

    expect(screen.getByText("Systems Architect")).toBeInTheDocument();
    expect(screen.getByText("Anthropic · Claude 3.5 Sonnet")).toBeInTheDocument();
    expect(screen.getByText("Systems Architect response round 1")).toBeInTheDocument();
  });

  it("maintains column alignment with placeholders when a persona did not speak in a round", () => {
    const mockEvents: DebateEvent[] = [
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Optimist round 1 speech",
        round: 1,
      } as any,
      {
        type: "seat_message",
        seat_name: "Systems Architect",
        content: "Systems Architect round 1 speech",
        round: 1,
      } as any,
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Optimist round 2 speech",
        round: 2,
      } as any,
    ];

    render(<RoundGrid events={mockEvents} />);

    // We have round 1 and round 2 headers
    expect(screen.getByText("Round 1 Deliberation")).toBeInTheDocument();
    expect(screen.getByText("Round 2 Deliberation")).toBeInTheDocument();

    // In round 2, Systems Architect didn't speak. Check for placeholder card
    expect(screen.getByText("No statement recorded from Systems Architect this round.")).toBeInTheDocument();
  });

  it("handles expand and collapse toggle behavior for long text cards", () => {
    // Generate a long text statement (> 350 characters)
    const longSpeechText = "A".repeat(400);

    const mockEvents: DebateEvent[] = [
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: longSpeechText,
        round: 1,
      } as any,
    ];

    render(<RoundGrid events={mockEvents} />);

    // Check that Show more button is present
    const toggleButton = screen.getByRole("button", { name: "Show more" });
    expect(toggleButton).toBeInTheDocument();

    // Click to expand
    fireEvent.click(toggleButton);
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByRole("button", { name: "Show less" }));
    expect(screen.getByRole("button", { name: "Show more" })).toBeInTheDocument();
  });
});
