import ParliamentRunView from "@/components/parliament/ParliamentRunView";
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
  params?: Promise<{ id: string }>;
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await (params ?? Promise.resolve({ id: "" }));

  let debate: any;
  let report: any;
  let eventPayload: any;
  let memberPayload: any;

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
          <p className="text-sm text-muted-foreground">
            This run is unavailable or you do not have access.
          </p>
          <a
            href="/runs"
            className="mt-3 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
          >
            Back to runs
          </a>
        </div>
      </main>
    );
  }

  const events: DebateEvent[] = Array.isArray(eventPayload?.items)
    ? eventPayload.items
    : [];

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
    (item): item is JudgeScoreEvent => item.type === "score",
  );

  const aggregatedScores: ScoreItem[] = eventScores.length
    ? Array.from(
        eventScores.reduce<Map<string, JudgeScoreEvent[]>>((acc, score) => {
          const list = acc.get(score.persona) ?? [];
          list.push(score);
          acc.set(score.persona, list);
          return acc;
        }, new Map()),
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

  const fallbackScores: ScoreItem[] = Array.isArray(report?.scores)
    ? report.scores.map((entry: any) => ({
        persona: entry.persona ?? "Agent",
        score:
          typeof entry.score === "number" ? entry.score : Number(entry.score ?? 0),
        rationale: entry.rationale,
      }))
    : [];

  const scores = aggregatedScores.length ? aggregatedScores : fallbackScores;

  const ranking = scores.length
    ? [...scores].sort((a, b) => b.score - a.score).map((s) => s.persona)
    : [];

  const vote: VotePayload | undefined = ranking.length
    ? { method: "borda", ranking }
    : undefined;

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

  const pairwiseEvents = events.filter(
    (event): event is PairwiseEvent => event.type === "pairwise",
  );

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

  const status = debate?.status ?? "queued";
  const createdAt =
    debate?.created_at && typeof debate.created_at === "string"
      ? new Date(debate.created_at).toLocaleString()
      : undefined;
  const updatedAt =
    debate?.updated_at && typeof debate.updated_at === "string"
      ? new Date(debate.updated_at).toLocaleString()
      : undefined;

  return (
    <main id="main" className="space-y-6 p-4 lg:p-6">
      <section className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">Run detail</p>
        <h1 className="heading-serif text-2xl font-semibold text-amber-900 dark:text-amber-50">
          {debate?.prompt ?? "Parliament session"}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-amber-900/80 dark:text-amber-100/80">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
            Status: {status}
          </span>
          {debate?.model_id ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
              Model: {debate.model_id}
            </span>
          ) : null}
          {createdAt ? <span>Created {createdAt}</span> : null}
          {updatedAt ? <span>Updated {updatedAt}</span> : null}
        </div>
      </section>
      <ParliamentRunView
        id={id}
        debate={debate}
        scores={scores}
        vote={vote}
        events={events}
        members={memberList}
        judgeVotes={judgeVotes}
        threshold={threshold}
        voteBasis={voteBasis}
        apiBase={apiBase}
      />
    </main>
  );
}
