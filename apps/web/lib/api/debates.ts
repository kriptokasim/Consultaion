export type DebateTimelineEvent = {
  debate_id: string;
  event_id: string;
  ts: string;
  type: "system_notice" | "seat_message" | "round_start" | "round_end" | "debate_failed" | "debate_completed";
  round_index?: number | null;
  seat_id?: string | null;
  seat_label?: string | null;
  role?: string | null;
  provider?: string | null;
  model?: string | null;
  stance?: string | null;
  content?: string | null;
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
