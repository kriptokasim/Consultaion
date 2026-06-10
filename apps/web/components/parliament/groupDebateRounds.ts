import type { DebateEvent } from "./types";

export interface RoundSpeech {
  id: string;
  persona: string;
  speechText: string;
  round: number;
  provider?: string;
  at?: string;
  role: "agent" | "critic";
  event: DebateEvent;
}

export interface DebateRound {
  roundNumber: number;
  speeches: RoundSpeech[];
}

export function groupDebateRounds(events: DebateEvent[]): {
  rounds: DebateRound[];
  uniquePersonas: string[];
} {
  const speeches: RoundSpeech[] = [];
  const personaSet = new Set<string>();

  events.forEach((event, index) => {
    // Determine if the event is a speech from a debater (agent or critic)
    const isSeatMessage = event.type === "seat_message";
    const isAgentMessage = event.type === "message" && ((event as any).role === "agent" || (event as any).role === "critic");

    if (isSeatMessage || isAgentMessage) {
      const persona = isSeatMessage
        ? (event as any).seat_name
        : (event as any).actor;
      
      const speechText = isSeatMessage
        ? (event as any).content || (event as any).text
        : (event as any).text;

      if (!persona || !speechText) {
        return;
      }

      const round = typeof (event as any).round === "number" ? (event as any).round : 1;
      const provider = (event as any).provider ?? (event as any).model;
      const role = isSeatMessage ? "agent" : ((event as any).role ?? "agent");
      const at = (event as any).at ?? (event as any).ts;
      const id = (event as any).id ?? `${event.type}-${round}-${persona}-${index}`;

      speeches.push({
        id,
        persona,
        speechText,
        round,
        provider,
        at,
        role,
        event,
      });

      personaSet.add(persona);
    }
  });

  // Group speeches by round number
  const roundMap = new Map<number, RoundSpeech[]>();
  speeches.forEach((speech) => {
    const existing = roundMap.get(speech.round) || [];
    existing.push(speech);
    roundMap.set(speech.round, existing);
  });

  // Convert to sorted DebateRound array
  const rounds: DebateRound[] = Array.from(roundMap.entries())
    .map(([roundNumber, speechesInRound]) => ({
      roundNumber,
      // Keep speeches sorted by their persona name or timestamp if needed, but we will render them in column order anyway.
      speeches: speechesInRound,
    }))
    .sort((a, b) => a.roundNumber - b.roundNumber);

  const uniquePersonas = Array.from(personaSet).sort();

  return {
    rounds,
    uniquePersonas,
  };
}
