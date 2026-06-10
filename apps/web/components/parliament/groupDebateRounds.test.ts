import { describe, test, expect } from "vitest";
import { groupDebateRounds } from "./groupDebateRounds";
import type { DebateEvent } from "./types";

describe("groupDebateRounds helper", () => {
  test("returns empty rounds and personas for empty event list", () => {
    const { rounds, uniquePersonas } = groupDebateRounds([]);
    expect(rounds).toEqual([]);
    expect(uniquePersonas).toEqual([]);
  });

  test("filters out non-speech events", () => {
    const mockEvents: DebateEvent[] = [
      { type: "status", status: "running" } as any,
      { type: "score", persona: "Optimist", score: 8.5 } as any,
      { type: "pairwise", winner: "Optimist" } as any,
    ];
    const { rounds, uniquePersonas } = groupDebateRounds(mockEvents);
    expect(rounds).toEqual([]);
    expect(uniquePersonas).toEqual([]);
  });

  test("correctly groups seat_message and message events by round", () => {
    const mockEvents: DebateEvent[] = [
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Hello from Optimist",
        round: 1,
        provider: "openai:gpt-4o",
      } as any,
      {
        type: "message",
        actor: "Systems Architect",
        text: "Hello from Systems Architect",
        round: 1,
        role: "agent",
        provider: "anthropic:claude-3-5-sonnet",
      } as any,
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Optimist round 2 statement",
        round: 2,
        provider: "openai:gpt-4o",
      } as any,
    ];

    const { rounds, uniquePersonas } = groupDebateRounds(mockEvents);

    expect(uniquePersonas).toEqual(["Optimist", "Systems Architect"]);
    expect(rounds).toHaveLength(2);

    expect(rounds[0].roundNumber).toBe(1);
    expect(rounds[0].speeches).toHaveLength(2);
    
    // Check speech content
    const optimistSpeechR1 = rounds[0].speeches.find(s => s.persona === "Optimist");
    const architectSpeechR1 = rounds[0].speeches.find(s => s.persona === "Systems Architect");
    
    expect(optimistSpeechR1?.speechText).toBe("Hello from Optimist");
    expect(optimistSpeechR1?.provider).toBe("openai:gpt-4o");
    expect(optimistSpeechR1?.role).toBe("agent");

    expect(architectSpeechR1?.speechText).toBe("Hello from Systems Architect");
    expect(architectSpeechR1?.provider).toBe("anthropic:claude-3-5-sonnet");
    expect(architectSpeechR1?.role).toBe("agent");

    expect(rounds[1].roundNumber).toBe(2);
    expect(rounds[1].speeches).toHaveLength(1);
    expect(rounds[1].speeches[0].persona).toBe("Optimist");
    expect(rounds[1].speeches[0].speechText).toBe("Optimist round 2 statement");
  });

  test("defaults round to 1 if not specified in speech event", () => {
    const mockEvents: DebateEvent[] = [
      {
        type: "seat_message",
        seat_name: "Optimist",
        content: "Round-less content",
      } as any,
    ];

    const { rounds } = groupDebateRounds(mockEvents);
    expect(rounds).toHaveLength(1);
    expect(rounds[0].roundNumber).toBe(1);
    expect(rounds[0].speeches[0].speechText).toBe("Round-less content");
  });

  test("handles role critic correctly", () => {
    const mockEvents: DebateEvent[] = [
      {
        type: "message",
        actor: "Optimist",
        text: "Critics content",
        round: 1,
        role: "critic",
      } as any,
    ];

    const { rounds } = groupDebateRounds(mockEvents);
    expect(rounds[0].speeches[0].role).toBe("critic");
  });
});
