import VotingSection from "@/components/parliament/VotingSection";
import DebateView from "@/components/parliament/DebateView";
import ExportButton from "@/components/parliament/ExportButton";
import ExportCSVButton from "@/components/parliament/ExportCSVButton";
import ParliamentChamber from "@/components/parliament/ParliamentChamber";
import type { ScoreItem, VotePayload, DebateEvent, JudgeScoreEvent, Member } from "@/components/parliament/types";
import { getDebate, getReport, getEvents, getDebateMembers } from "@/lib/api";

export const dynamic = "force-dynamic";

type RunDetailProps = {
  params: Promise<{ id: string }>;
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await params;
  const [debate, report, eventPayload, memberPayload] = await Promise.all([
    getDebate(id),
    getReport(id),
    getEvents(id),
    getDebateMembers(id),
  ]);

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
