export type DebateTimelineEvent = {
  ts: string;
  debateId: string;
  roundIndex: number;
  phase: "draft" | "critique" | "judge" | "synthesis" | string;
  seatId: string;
  seatRole: string;
  provider?: string | null;
  model?: string | null;
  eventType: "seat_message" | "system_notice" | "score_update" | "summary";
  content?: string | null;
  stance?: string | null;
  reasoning?: string | null;
  score?: number | null;
  meta?: Record<string, unknown> | null;
};

export async function fetchDebateTimeline(debateId: string): Promise<DebateTimelineEvent[]> {
  const res = await fetch(`/api/debates/${debateId}/timeline`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const error = new Error("Failed to load debate timeline");
    (error as any).status = res.status;
    throw error;
  }
  return res.json();
}
