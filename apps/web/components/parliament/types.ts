export type Role = "agent" | "critic" | "judge" | "synthesizer";

export interface Member {
  id: string;
  name: string;
  role: Role;
  party?: string;
}

export interface ScoreItem {
  persona: string;
  score: number;
  rationale?: string;
}

export interface VotePayload {
  method: "borda" | "condorcet" | "plurality" | "approval";
  ranking: string[];
}

export interface DebateEvent {
  type: "message" | "score" | "final" | "notice";
  round?: number;
  actor?: string;
  role?: Role;
  text?: string;
  scores?: ScoreItem[];
}
