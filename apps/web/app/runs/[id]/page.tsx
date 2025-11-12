import VotingSection from "@/components/parliament/VotingSection";
import DebateView from "@/components/parliament/DebateView";
import ExportButton from "@/components/parliament/ExportButton";
import ExportCSVButton from "@/components/parliament/ExportCSVButton";
import ParliamentChamber from "@/components/parliament/ParliamentChamber";
import type { ScoreItem, VotePayload, DebateEvent, JudgeScoreEvent, Member } from "@/components/parliament/types";
import { fetchWithAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

type RunDetailProps = {
  params: Promise<{ id: string }>;
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await params;
  let debate: any, report: any, eventPayload: any, memberPayload: any;
  try {
    const [debateRes, reportRes, eventsRes, membersRes] = await Promise.all([
      fetchWithAuth(`/debates/${id}`),
      fetchWithAuth(`/debates/${id}/report`),
      fetchWithAuth(`/debates/${id}/events`),
      fetchWithAuth(`/debates/${id}/members`),
    ]);
    if ([debateRes, reportRes, eventsRes, membersRes].some((res) => !res.ok)) {
      throw new Error("unauthorized");
    }
    [debate, report, eventPayload, memberPayload] = await Promise.all([
      debateRes.json(),
      reportRes.json(),
      eventsRes.json(),
      membersRes.json(),
    ]);
  } catch (error) {
    return (
      <main id="main" className="flex h-full items-center justify-center p-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">This run is unavailable or you do not have access.</p>
          <a href="/runs" className="mt-3 inline-flex items-center rounded bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Back to Runs
          </a>
        </div>
      </main>
    );
  }

  const events: DebateEvent[] = Array.isArray(eventPayload?.items) ? eventPayload.items : [];

  if (debate?.final_content) {
    events.push({
      type: "final",
      actor: "Synthesizer",
      role: "synthesizer",
      text: debate.final_content,
      at: typeof debate.updated_at === "string" ? debate.updated_at : undefined,
    });
  }

  const eventScores = events.filter(
    (item): item is JudgeScoreEvent => item.type === "score"
  );

  const aggregatedScores: ScoreItem[] = eventScores.length
    ? Array.from(
        eventScores.reduce<Map<string, JudgeScoreEvent[]>>((acc, score) => {
          const list = acc.get(score.persona) ?? [];
          list.push(score);
          acc.set(score.persona, list);
          return acc;
        }, new Map())
      ).map(([persona, entries]) => {
        const total = entries.reduce((sum, entry) => sum + entry.score, 0);
        const avg = entries.length ? total / entries.length : 0;
        const last = entries[entries.length - 1];
        return {
          persona,
          score: Number(avg.toFixed(2)),
          rationale: last?.rationale,
        };
      })
    : [];

  const fallbackScores = Array.isArray(report?.scores)
    ? report.scores.map((entry: any) => ({
        persona: entry.persona ?? "Agent",
        score: typeof entry.score === "number" ? entry.score : Number(entry.score ?? 0),
        rationale: entry.rationale,
      }))
    : [];

  const scores = aggregatedScores.length ? aggregatedScores : fallbackScores;

  const ranking = scores.length ? [...scores].sort((a, b) => b.score - a.score).map((s) => s.persona) : [];
  const vote: VotePayload | undefined = ranking.length ? { method: "borda", ranking } : undefined;

  const memberList: Member[] = Array.isArray(memberPayload?.members)
    ? memberPayload.members.map((member: any) => ({
        id: member.id ?? member.name,
        name: member.name ?? member.id,
        role: member.role ?? "agent",
        party: member.party,
      }))
    : [];

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <main id="main" className="space-y-6 p-4">
      {memberList.length ? (
        <ParliamentChamber members={memberList} layout="benches" />
      ) : null}
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex-1">
          <VotingSection scores={scores} vote={vote} />
        </div>
        <div className="flex w-full flex-col gap-4 items-center lg:w-64 lg:self-center">
          <ExportButton debateId={id} apiBase={apiBase} />
          <ExportCSVButton debateId={id} apiBase={apiBase} />
        </div>
      </div>
      <DebateView events={events} />
    </main>
  );
}
