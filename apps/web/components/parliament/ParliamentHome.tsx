import { Sparkles, Clock, Users, Trophy } from "lucide-react";
import Brand from "@/components/parliament/Brand";
import type { Member, ScoreItem } from "./types";

interface ParliamentHomeProps {
  members: Member[];
  activeMemberId?: string;
  speakerSeconds?: number;
  stats?: {
    rounds: number;
    speeches: number;
    votes: number;
  };
  voteResults?: ScoreItem[];
  onStart?: () => void;
  running?: boolean;
}

const gradientRing =
  "before:absolute before:inset-0 before:rounded-full before:bg-gradient-to-r before:from-amber-400/30 before:to-amber-200/20 before:blur-3xl before:content-['']";

export default function ParliamentHome({
  members,
  activeMemberId,
  speakerSeconds = 0,
  stats,
  voteResults,
  onStart,
  running,
}: ParliamentHomeProps) {
  const activeMember = members.find((member) => member.id === activeMemberId);
  const topScores = (voteResults ?? [])
    .slice()
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  return (
    <section className="relative overflow-hidden rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-stone-50 to-white p-6 shadow-[0_25px_60px_rgba(120,113,108,0.15)]">
      <div className="pointer-events-none absolute inset-0 opacity-40 [mask-image:radial-gradient(circle_at_center,white,transparent)]">
        <div className="absolute left-1/4 top-0 h-64 w-64 rounded-full bg-amber-100 blur-3xl" />
        <div className="absolute right-1/3 bottom-0 h-72 w-72 rounded-full bg-stone-200 blur-[110px]" />
      </div>
      <div className="relative grid gap-8 md:grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white/80 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-amber-700 shadow-sm">
            <Brand height={20} tone="amber" />
            <Sparkles className="h-4 w-4" />
            Sepia Parliament
          </div>
          <div className="space-y-4">
            <h1 className="text-4xl font-semibold leading-tight text-stone-900 sm:text-5xl">
              Coordinating <span className="text-amber-600">AI delegates</span>{" "}
              under parliamentary discipline.
            </h1>
            <p className="max-w-2xl text-base text-stone-600">
              The chamber pairs amber-lit ceremony with rigorous analytics so you
              can watch every intervention, transcript line, and score unfold in
              real time. Bring your own prompt and the parliament convenes in
              seconds.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={running}
              onClick={onStart}
              aria-pressed={running}
              aria-label="Summon a debate session"
              className="inline-flex items-center gap-2 rounded-full bg-amber-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-amber-600/30 transition hover:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Summon a Session
            </button>
            <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/80 px-4 py-2 text-sm font-medium text-stone-600 shadow-sm">
              <Clock className="h-4 w-4 text-amber-500" />
              <span aria-live="polite" aria-busy={running}>
                {running ? "Session in progress" : "Standing by"}
              </span>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              label="Active rounds"
              value={stats?.rounds ?? 0}
              icon={<Users className="h-4 w-4 text-amber-500" />}
            />
            <MetricCard
              label="Speeches logged"
              value={stats?.speeches ?? 0}
              icon={<Sparkles className="h-4 w-4 text-amber-500" />}
            />
            <MetricCard
              label="Votes recorded"
              value={stats?.votes ?? 0}
              icon={<Trophy className="h-4 w-4 text-amber-500" />}
            />
          </div>
        </div>
        <div className="space-y-4 rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-inner">
          <div className="rounded-xl border border-amber-100 bg-amber-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
              Current Speaker
            </p>
            {activeMember ? (
              <div className="mt-3 flex items-center gap-3">
                <div
                  className={`relative h-12 w-12 rounded-full bg-amber-600 text-center text-lg font-bold text-white ${gradientRing}`}
                >
                  <span className="relative leading-[48px]">
                    {activeMember.name.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="text-base font-semibold text-stone-900">
                    {activeMember.name}
                  </p>
                  <p className="text-xs uppercase tracking-wide text-stone-500">
                    Speaking for {speakerSeconds}s
                  </p>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-stone-500">
                Session idle — start a debate to brief the chamber.
              </p>
            )}
          </div>
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Latest Division
            </p>
            {topScores.length === 0 ? (
              <div className="rounded-lg border border-dashed border-stone-200 bg-stone-50/40 p-4 text-sm text-stone-500">
                Awaiting judges to issue their rulings.
              </div>
            ) : (
              topScores.map((score, index) => (
                <VoteBar
                  key={score.persona}
                  persona={score.persona}
                  score={score.score}
                  highlight={index === 0}
                />
              ))
            )}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Members present
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {members.slice(0, 6).map((member) => (
                <span
                  key={member.id}
                  className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/70 px-3 py-1 text-xs font-medium text-stone-600"
                >
                  <span className="inline-flex h-2 w-2 rounded-full bg-amber-500" />
                  {member.name}
                </span>
              ))}
              {members.length > 6 && (
                <span className="text-xs text-stone-500">
                  +{members.length - 6} more
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white/80 p-4 shadow-inner">
      <div className="flex items-center justify-between text-stone-500">
        <span className="text-xs font-semibold uppercase tracking-wide">
          {label}
        </span>
        {icon}
      </div>
      <p className="mt-3 text-2xl font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function VoteBar({
  persona,
  score,
  highlight,
}: {
  persona: string;
  score: number;
  highlight?: boolean;
}) {
  return (
    <div className="space-y-1 rounded-xl border border-stone-100 bg-stone-50/60 p-3">
      <div className="flex items-center justify-between text-sm text-stone-600">
        <span className="font-medium text-stone-800">{persona}</span>
        <span className="font-mono text-stone-500">{score.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-stone-200/70">
        <div
          className={`h-full rounded-full ${
            highlight
              ? "bg-gradient-to-r from-amber-500 to-amber-300"
              : "bg-gradient-to-r from-stone-400 to-stone-300"
          }`}
          style={{ width: `${Math.min(100, (score / 10) * 100)}%` }}
        />
      </div>
    </div>
  );
}
