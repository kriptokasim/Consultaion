\"use client\";

import { useMemo, useRef, useState } from "react";
import VotingSection from "./VotingSection";
import DebateView from "./DebateView";
import ExportButton from "./ExportButton";
import ExportCSVButton from "./ExportCSVButton";
import HansardTranscript from "./HansardTranscript";
import SummaryCard from "./SummaryCard";
import ScoreboardCard from "./ScoreboardCard";
import VotingChamber from "./VotingChamber";
import StatusBadge from "./StatusBadge";

import type {
  ScoreItem,
  VotePayload,
  DebateEvent,
  Member,
  JudgeVoteFlow,
  JudgeScoreEvent,
} from "./types";

interface ParliamentRunViewProps {
  id: string;
  debate: any;
  scores: ScoreItem[];
  vote?: VotePayload;
  events: DebateEvent[];
  members: Member[];
  judgeVotes: JudgeVoteFlow[];
  threshold: number;
  voteBasis: "pairwise" | "threshold";
  apiBase: string;
}

interface ModelAnswer {
  persona: string;
  score?: number;
  fullText?: string;
  snippet?: string;
  rounds?: number[];
}

export default function ParliamentRunView({
  id,
  debate,
  scores,
  vote,
  events,
  members,
  judgeVotes,
  threshold,
  voteBasis,
  apiBase,
}: ParliamentRunViewProps) {
  const [transcriptMode, setTranscriptMode] = useState<"highlights" | "full">("highlights");
  const answerRefs = useRef<Record<string, HTMLDetailsElement | null>>({});
  const sortedScores = scores.slice().sort((a, b) => b.score - a.score);

  const winnerPersona =
    (vote?.ranking && vote.ranking[0]) ||
    (sortedScores[0] ? sortedScores[0].persona : undefined);

  const winnerScore = winnerPersona
    ? sortedScores.find((s) => s.persona === winnerPersona)?.score
    : undefined;

  const hasTie =
    sortedScores.length > 1 &&
    sortedScores[0] &&
    sortedScores[1].score === sortedScores[0].score;

  const finalEvent = [...events]
    .reverse()
    .find((event) => event.type === "final" && "text" in event && event.text) as
    | (DebateEvent & { text?: string; actor?: string })
    | undefined;

  const championText = finalEvent?.text;
  const championActor = finalEvent?.actor || "Synthesizer";

  const createdAt =
    debate?.created_at && typeof debate.created_at === "string"
      ? new Date(debate.created_at).toLocaleString()
      : "—";

  const updatedAt =
    debate?.updated_at && typeof debate.updated_at === "string"
      ? new Date(debate.updated_at).toLocaleString()
    : "—";

  const methodLabel = vote?.method
    ? {
        borda: "Borda Count",
        condorcet: "Condorcet Method",
        plurality: "Plurality Voting",
        approval: "Approval Voting",
      }[vote.method] ?? vote.method
    : undefined;

  const modelAnswers = buildModelAnswers(events, sortedScores);
  const ranking = vote?.ranking && vote.ranking.length ? vote.ranking : sortedScores.map((s) => s.persona);
  const scoreMap = useMemo(() => {
    const map = new Map<string, number>();
    sortedScores.forEach((entry) => map.set(entry.persona, entry.score));
    return map;
  }, [sortedScores]);
  const scoreboardPills = ranking.map((persona, index) => ({
    persona,
    rank: index + 1,
    score: scoreMap.get(persona),
  }));

  const eventScores = useMemo(
    () => events.filter((item): item is JudgeScoreEvent => item.type === "score"),
    [events],
  );
  const championReasons = useMemo(
    () =>
      eventScores
        .map((entry) => entry.rationale)
        .filter((text): text is string => Boolean(text && text.trim()))
        .slice(0, 3),
    [eventScores],
  );

  const highlightEvents = useMemo(() => {
    const messages = events.filter((event) => event.type === "message");
    const finals = events.filter((event) => event.type === "final");
    const scoresOnly = eventScores;
    const allowed = new Set<DebateEvent>();
    messages.slice(0, 3).forEach((msg) => allowed.add(msg));
    finals.forEach((evt) => allowed.add(evt));
    scoresOnly.forEach((evt) => allowed.add(evt));
    return events.filter((evt) => allowed.has(evt));
  }, [eventScores, events]);

  const transcriptEvents = transcriptMode === "highlights" ? highlightEvents : events;

  const scrollToAnswer = (persona: string) => {
    const node = answerRefs.current[persona];
    if (node) {
      node.open = true;
      node.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div className="space-y-6">
      {/* Hero header: amber / sepia theme */}
      <section className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
              AI Parliament Session
            </p>
            <h1 className="text-2xl font-semibold text-stone-900 md:text-3xl">
              Run #{id}
            </h1>
            <p className="text-sm leading-relaxed text-stone-700">
              {debate?.prompt ?? "No prompt available for this run."}
            </p>
          </div>

          <div className="flex flex-col items-start gap-3 md:items-end">
            <StatusBadge status={debate?.status} />
            <dl className="grid gap-3 text-xs text-stone-600">
              <div>
                <dt className="uppercase tracking-wide text-[0.65rem] text-stone-400">
                  Voting method
                </dt>
                <dd className="mt-1 font-medium text-stone-900">
                  {methodLabel ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-[0.65rem] text-stone-400">
                  Created
                </dt>
                <dd className="mt-1">{createdAt}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-[0.65rem] text-stone-400">
                  Updated
                </dt>
                <dd className="mt-1">{updatedAt}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {scoreboardPills.length ? (
        <div className="rounded-3xl border border-amber-100 bg-amber-50/70 p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-amber-800">
            <span>Scoreboard</span>
            <span className="text-amber-700">Judge-ranked standings</span>
          </div>
          <div className="flex flex-wrap gap-3 sm:flex-nowrap sm:overflow-x-auto">
            {scoreboardPills.map((entry) => {
              const isChampion = entry.rank === 1;
              return (
                <button
                  key={entry.persona}
                  type="button"
                  onClick={() => scrollToAnswer(entry.persona)}
                  className={`group inline-flex min-w-[9rem] items-center justify-between rounded-2xl border px-3 py-2 text-left text-sm shadow-sm transition ${
                    isChampion
                      ? "border-amber-500 bg-white text-amber-900 ring-2 ring-amber-200"
                      : "border-amber-100 bg-white/70 text-stone-800 hover:border-amber-300"
                  }`}
                  aria-label={`View answer from ${entry.persona}`}
                >
                  <div className="flex flex-col">
                    <span className="text-xs uppercase tracking-wide text-amber-600">
                      Rank #{entry.rank}
                    </span>
                    <span className="font-semibold text-stone-900">{entry.persona}</span>
                  </div>
                  {typeof entry.score === "number" ? (
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-mono ${
                        isChampion
                          ? "bg-amber-100 text-amber-800"
                          : "bg-stone-100 text-stone-700"
                      }`}
                    >
                      {entry.score.toFixed(2)}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {/* Champion answer + scoreboard */}
      <section className="grid gap-6 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1.4fr)]">
        <SummaryCard
          title="Winning Answer"
          description="Ranked #1 by AI judges in this session."
        >
          <div className="space-y-4">
            <ChampionSummary
              persona={winnerPersona}
              score={winnerScore}
              hasTie={hasTie}
              actor={championActor}
              text={championText}
              reasons={championReasons}
            />

            <a
              href="#answers"
              className="inline-flex items-center gap-2 text-sm font-semibold text-amber-800 hover:text-amber-700"
            >
              View full debate details ↴
            </a>
          </div>
        </SummaryCard>

        <SummaryCard
          title="Judge’s Scoreboard"
          description="How each persona performed across the debate."
        >
          <ScoreboardCard scores={scores} method={vote?.method} />
          <div className="mt-4 flex flex-wrap gap-3">
            <ExportButton debateId={id} apiBase={apiBase} />
            <ExportCSVButton debateId={id} apiBase={apiBase} />
          </div>
        </SummaryCard>
      </section>

      {/* All model answers ("show more" style) */}
      <SummaryCard
        id="answers"
        title="Model answers"
        description="Each model’s own answer to the prompt, ordered by their final score."
      >
        {modelAnswers.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/80 p-4 text-sm text-stone-500">
            No agent messages were recorded for this run.
          </p>
        ) : (
          <div className="space-y-3">
            {modelAnswers.map((answer) => (
              <details
                key={answer.persona}
                ref={(node) => {
                  if (node) {
                    answerRefs.current[answer.persona] = node;
                  }
                }}
                className="group rounded-2xl border border-stone-200 bg-white/85 p-3 shadow-sm transition hover:shadow-md"
              >
                <summary className="flex cursor-pointer flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium text-stone-900">{answer.persona}</span>
                    {typeof answer.score === "number" && (
                      <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-mono text-amber-700">
                        {answer.score.toFixed(2)}
                      </span>
                    )}
                    {answer.rounds && answer.rounds.length > 0 && (
                      <span className="inline-flex items-center rounded-full bg-stone-50 px-2 py-0.5 text-[0.7rem] text-stone-600">
                        Rounds {Array.from(new Set(answer.rounds)).sort((a, b) => a - b).join(", ")}
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-stone-600">
                    {answer.snippet ? (
                      <span>{answer.snippet}</span>
                    ) : (
                      <span className="italic text-stone-400">No text captured for this persona.</span>
                    )}
                    <span className="ml-2 text-amber-700 group-open:hidden">Show full answer</span>
                    <span className="ml-2 hidden text-amber-700 group-open:inline">Hide answer</span>
                  </div>
                </summary>

                {answer.fullText && (
                  <div className="mt-3 border-t border-stone-100 pt-3">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-800">
                      {answer.fullText}
                    </p>
                  </div>
                )}
              </details>
            ))}
          </div>
        )}
      </SummaryCard>

      {/* Parliament chamber visualization + decision explanation */}
      <SummaryCard
        title="Division in the Chamber"
        description={
          voteBasis === "pairwise"
            ? "Visualizing pairwise judge preferences between personas."
            : `Visualizing judge scores against a threshold of ${threshold}.`
        }
      >
        <div className="space-y-4">
          {/* Mini chamber map inspired by real seating diagrams */}
          <MiniChamberMap winnerPersona={winnerPersona} />

          <div className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4">
            <VotingChamber
              scores={scores}
              members={members}
              threshold={threshold}
              flows={judgeVotes}
              basis={voteBasis}
            />
          </div>

          <VotingSection scores={scores} vote={vote} />
        </div>
      </SummaryCard>

      {/* Hansard + live timeline */}
      <section className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)]">
        <SummaryCard
          title="Hansard transcript"
          description="Line-by-line proceedings of the AI Parliament session."
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
            <button
              type="button"
              onClick={() => setTranscriptMode("highlights")}
              className={`rounded-full px-3 py-1 ${
                transcriptMode === "highlights" ? "bg-amber-200 text-amber-900 shadow-sm" : ""
              }`}
            >
              Highlights
            </button>
            <button
              type="button"
              onClick={() => setTranscriptMode("full")}
              className={`rounded-full px-3 py-1 ${
                transcriptMode === "full" ? "bg-amber-200 text-amber-900 shadow-sm" : ""
              }`}
            >
              Full transcript
            </button>
          </div>
          <HansardTranscript events={transcriptEvents} members={members} />
        </SummaryCard>

        <SummaryCard
          title="Live timeline"
          description="Raw events emitted during the run."
        >
          <DebateView events={events} />
        </SummaryCard>
      </section>
    </div>
  );
}

function buildModelAnswers(events: DebateEvent[], sortedScores: ScoreItem[]): ModelAnswer[] {
  // Treat all agent messages as model answers, grouped by persona
  const agentMessages = events.filter(
    (event) => event.type === "message" && (event as any).role === "agent",
  ) as Array<DebateEvent & { actor?: string; text?: string; round?: number }>;

  const byPersona = new Map<string, { fullText: string; rounds: number[] }>();

  for (const event of agentMessages) {
    const actor = (event as any).actor as string | undefined;
    const text = (event as any).text as string | undefined;
    const round = (event as any).round as number | undefined;
    if (!actor || !text) continue;

    const existing = byPersona.get(actor) ?? { fullText: "", rounds: [] as number[] };
    existing.fullText = existing.fullText ? `${existing.fullText}\n\n${text}` : text;
    if (typeof round === "number") existing.rounds.push(round);
    byPersona.set(actor, existing);
  }

  const result: ModelAnswer[] = [];

  // First, follow the score ordering so the list matches the scoreboard
  for (const score of sortedScores) {
    const entry = byPersona.get(score.persona);
    result.push({
      persona: score.persona,
      score: score.score,
      fullText: entry?.fullText,
      snippet: makeSnippet(entry?.fullText),
      rounds: entry?.rounds,
    });
  }

  // Then append any personas that spoke but have no explicit score
  for (const [persona, entry] of Array.from(byPersona.entries())) {
    if (!sortedScores.some((s) => s.persona === persona)) {
      result.push({
        persona,
        fullText: entry.fullText,
        snippet: makeSnippet(entry.fullText),
        rounds: entry.rounds,
      });
    }
  }

  return result;
}

function makeSnippet(text?: string, limit = 220): string | undefined {
  if (!text) return undefined;
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}…`;
}

function ChampionSummary({
  persona,
  score,
  hasTie,
  actor,
  text,
  reasons,
}: {
  persona?: string;
  score?: number;
  hasTie: boolean;
  actor?: string;
  text?: string;
  reasons: string[];
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-800">
          Winning answer
        </span>
        {persona ? (
          <span className="text-sm font-medium text-stone-900">
            {persona}
            {typeof score === "number" ? (
              <span className="ml-2 inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-mono text-amber-700">
                {score.toFixed(2)}
              </span>
            ) : null}
          </span>
        ) : (
          <span className="text-sm text-stone-500">No winner yet</span>
        )}
        {hasTie ? (
          <span className="text-xs text-amber-700">
            Tie detected – voting method was used to break the tie.
          </span>
        ) : null}
      </div>

      {text ? (
        <div className="rounded-2xl border border-amber-100 bg-amber-50/90 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
            {actor || "Synthesizer"}
          </p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-800">{text}</p>
          {reasons.length ? (
            <div className="mt-3 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Why it won</p>
              <ul className="list-disc space-y-1 pl-5 text-sm text-stone-800">
                {reasons.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/80 p-4 text-sm text-stone-500">
          No synthesized final answer was recorded for this run. You can still inspect all individual speeches in the
          model answers and Hansard transcript below.
        </p>
      )}
    </div>
  );
}

function MiniChamberMap({ winnerPersona }: { winnerPersona?: string }) {
  return (
    <div className="mb-4 rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="max-w-xs space-y-1 text-xs text-amber-900">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-amber-800">
            Chamber schematic
          </h3>
          <p>
            Inspired by real parliamentary seating: agent benches on the left, critics on the
            right, judges and the synthesizer at the table.
          </p>
          {winnerPersona && (
            <p className="pt-1 text-[0.7rem] font-medium">
              Current winning model: <span className="font-semibold">{winnerPersona}</span>
            </p>
          )}
        </div>

        <div className="flex items-center justify-center gap-3">
          {/* Government / agents */}
          <div className="flex items-end gap-1" aria-label="Agent benches">
            {Array.from({ length: 5 }).map((_, index) => (
              <MiniSeat key={`agent-${index}`} label="Agent bench" color="bg-emerald-500/85" />
            ))}
          </div>

          {/* Table + chair */}
          <div className="flex flex-col items-center gap-1" aria-label="Chair and table">
            <MiniSeat label="Speaker" color="bg-stone-700" />
            <MiniSeat label="Judges & synthesizer" color="bg-amber-400/90" />
          </div>

          {/* Opposition / critics */}
          <div className="flex items-end gap-1" aria-label="Critic benches">
            {Array.from({ length: 5 }).map((_, index) => (
              <MiniSeat key={`critic-${index}`} label="Critic bench" color="bg-orange-400/90" />
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1 text-[0.65rem] text-amber-900">
          <div className="flex items-center gap-2">
            <span className="h-2 w-3 rounded-[3px] bg-emerald-500/85" aria-hidden="true" />
            <span>Agent benches (model advocates)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-3 rounded-[3px] bg-orange-400/90" aria-hidden="true" />
            <span>Critic benches / opposition</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-3 rounded-[3px] bg-stone-700" aria-hidden="true" />
            <span>Speaker’s chair</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniSeat({ label, color }: { label: string; color: string }) {
  return (
    <div
      className={`h-3 w-4 rounded-[3px] border border-amber-700/40 shadow-sm ${color}`}
      aria-label={label}
      title={label}
    />
  );
}
