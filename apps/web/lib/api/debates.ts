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

import { fetchWithAuth } from "../auth";

export async function fetchDebateTimeline(debateId: string): Promise<DebateTimelineEvent[]> {
  const res = await fetchWithAuth(`/debates/${debateId}/timeline`);
  if (!res.ok) {
    throw new Error("Failed to fetch timeline");
  }
  return res.json();
}
