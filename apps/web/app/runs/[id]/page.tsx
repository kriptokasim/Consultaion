import VotingSection from "@/components/parliament/VotingSection";
import DebateView from "@/components/parliament/DebateView";
import ExportButton from "@/components/parliament/ExportButton";
import ExportCSVButton from "@/components/parliament/ExportCSVButton";
import HansardTranscript from "@/components/parliament/HansardTranscript";
import SummaryCard from "@/components/parliament/SummaryCard";
import ScoreboardCard from "@/components/parliament/ScoreboardCard";
import VotingChamber from "@/components/parliament/VotingChamber";
import type {
  ScoreItem,
  VotePayload,
  DebateEvent,
  JudgeScoreEvent,
  Member,
  JudgeVoteFlow,
  PairwiseEvent,
} from "@/components/parliament/types";
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
  const threshold = Number(process.env.NEXT_PUBLIC_VOTE_THRESHOLD ?? "7");

  const pairwiseEvents = events.filter((event): event is PairwiseEvent => event.type === "pairwise");
  let voteBasis: "pairwise" | "threshold" = "threshold";
  let judgeVotes: JudgeVoteFlow[] = [];
  if (pairwiseEvents.length > 0) {
    voteBasis = "pairwise";
    judgeVotes = pairwiseEvents.map((entry) => ({
      persona: entry.winner,
      judge: entry.judge ?? "division",
      score: 1,
      at: entry.at,
      vote: "aye",
    }));
  } else {
    judgeVotes = eventScores.map((entry) => ({
      persona: entry.persona,
      judge: entry.judge,
      score: entry.score,
      at: entry.at,
      vote: entry.score >= threshold ? ("aye" as const) : ("nay" as const),
    }));
  }

  return (
    <main id="main" className="space-y-6 p-4">
      <SummaryCard title="Debate Summary" description="High-level run metadata">
        <dl className="grid gap-4 text-sm text-stone-600 md:grid-cols-2">
          <div>
            <dt className="uppercase tracking-wide text-xs text-stone-400">Prompt</dt>
            <dd className="mt-1 text-stone-900">{debate?.prompt ?? "—"}</dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide text-xs text-stone-400">Status</dt>
            <dd className="mt-1">
              <StatusBadge status={debate?.status} />
            </dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide text-xs text-stone-400">Created</dt>
            <dd className="mt-1 text-stone-900">
              {debate?.created_at ? new Date(debate.created_at).toLocaleString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide text-xs text-stone-400">Updated</dt>
            <dd className="mt-1 text-stone-900">
              {debate?.updated_at ? new Date(debate.updated_at).toLocaleString() : "—"}
            </dd>
          </div>
        </dl>
      </SummaryCard>

      <SummaryCard title="Aggregate Scores" description="Judge tallies from the latest division">
        <ScoreboardCard scores={scores} method={vote?.method} />
        <div className="mt-4 flex flex-wrap gap-3">
          <ExportButton debateId={id} apiBase={apiBase} />
          <ExportCSVButton debateId={id} apiBase={apiBase} />
        </div>
      </SummaryCard>

      <VotingChamber scores={scores} members={memberList} threshold={threshold} flows={judgeVotes} basis={voteBasis} />
      <VotingSection scores={scores} vote={vote} />
      <HansardTranscript events={events} members={memberList} />

      <SummaryCard title="Live timeline" description="Raw events emitted during the run">
        <DebateView events={events} />
      </SummaryCard>
    </main>
  );
}
import StatusBadge from "@/components/parliament/StatusBadge";
