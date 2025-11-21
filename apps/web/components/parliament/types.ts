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

export interface JudgeScoreEvent {
  type: "score";
  persona: string;
  judge: string;
  score: number;
  rationale?: string;
  at?: string;
  role?: Role;
}

export type JudgeVoteFlow = {
  persona: string;
  judge: string;
  score: number;
  vote: "aye" | "nay";
  at?: string;
};

export interface PairwiseEvent {
  type: "pairwise";
  winner: string;
  loser: string;
  judge?: string;
  user_id?: string;
  category?: string | null;
  at?: string;
}

export type DebateEvent =
  | {
      type: "message";
      round?: number;
      actor?: string;
      role?: Role;
      text?: string;
      at?: string;
      seatId?: string;
      provider?: string;
      model?: string;
    }
  | JudgeScoreEvent
  | PairwiseEvent
  | {
      type: "final";
      actor?: string;
      text?: string;
      at?: string;
      role?: Role;
    }
  | {
      type: "notice";
      text?: string;
      at?: string;
      role?: Role;
    };
