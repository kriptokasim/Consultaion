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
    <section className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-accent-secondary/5 via-secondary to-card p-6 shadow-smooth-lg">
      <div className="pointer-events-none absolute inset-0 opacity-40 [mask-image:radial-gradient(circle_at_center,white,transparent)]">
        <div className="absolute left-1/4 top-0 h-64 w-64 rounded-full bg-accent-secondary/10 blur-3xl" />
        <div className="absolute right-1/3 bottom-0 h-72 w-72 rounded-full bg-muted blur-[110px]" />
      </div>
      <div className="relative grid gap-8 md:grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent-secondary/30 bg-card/80 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-accent-secondary shadow-sm">
            <Brand height={20} tone="amber" />
            <Sparkles className="h-4 w-4" />
            Sepia Parliament
          </div>
          <div className="space-y-4">
            <h1 className="text-4xl font-semibold leading-tight text-foreground sm:text-5xl">
              One question. <span className="text-accent-secondary">Many AI models.</span> One champion answer.
            </h1>
            <p className="max-w-2xl text-base text-muted-foreground">
              Ask a single question and let multiple AI models draft their answers. Judges cross-examine them, score every
              speech, and Consultaion returns one champion answer back to you.
            </p>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Start by entering a question below, then <strong>Summon a Session</strong>. You can watch the full debate,
              scores, and final ruling in real time.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={running}
              onClick={onStart}
              aria-pressed={running}
              aria-label="Summon a debate session"
              className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-smooth transition hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Summon a Session
            </button>
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/40 px-4 py-2 text-sm font-medium text-muted-foreground">
              <Clock className="h-4 w-4 text-accent-secondary" />
              <span aria-live="polite" aria-busy={running}>
                {running ? "Session in progress" : "Standing by"}
              </span>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              label="Active rounds"
              value={stats?.rounds ?? 0}
              icon={<Users className="h-4 w-4 text-accent-secondary" />}
            />
            <MetricCard
              label="Speeches logged"
              value={stats?.speeches ?? 0}
              icon={<Sparkles className="h-4 w-4 text-accent-secondary" />}
            />
            <MetricCard
              label="Votes recorded"
              value={stats?.votes ?? 0}
              icon={<Trophy className="h-4 w-4 text-accent-secondary" />}
            />
          </div>
        </div>
        <div className="space-y-4 rounded-2xl border border-border bg-card/80 p-4 shadow-inner">
          <div className="rounded-xl border border-accent-secondary/20 bg-accent-secondary/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-accent-secondary">
              Current Speaker
            </p>
            {activeMember ? (
              <div className="mt-3 flex items-center gap-3">
                <div
                  className="relative h-12 w-12 rounded-full bg-primary text-center text-lg font-bold text-primary-foreground"
                >
                  <span className="relative leading-[48px]">
                    {activeMember.name.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="text-base font-semibold text-foreground">
                    {activeMember.name}
                  </p>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Speaking for {speakerSeconds}s
                  </p>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Session idle — start a debate to brief the chamber.
              </p>
            )}
          </div>
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Latest Division
            </p>
            {topScores.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-secondary/40 p-4 text-sm text-muted-foreground">
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
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Members present
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {members.slice(0, 6).map((member) => (
                <span
                  key={member.id}
                  className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground"
                >
                  <span className="inline-flex h-2 w-2 rounded-full bg-accent-secondary" />
                  {member.name}
                </span>
              ))}
              {members.length > 6 && (
                <span className="text-xs text-muted-foreground">
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
    <div className="rounded-2xl border border-border bg-card p-4 shadow-smooth transition-transform duration-200 hover:-translate-y-[2px] hover:shadow-smooth-lg">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="text-[11px] font-semibold uppercase tracking-wide">
          {label}
        </span>
        <span className="inline-flex items-center justify-center rounded-full bg-accent-secondary/10 px-2 py-1 text-accent-secondary shadow-inner">
          {icon}
        </span>
      </div>
      <p className="mt-3 text-2xl font-semibold text-foreground">{value}</p>
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
    <div className="space-y-1 rounded-xl border border-border bg-secondary/60 p-3">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{persona}</span>
        <span className="font-mono text-muted-foreground">{score.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${highlight
              ? "bg-gradient-to-r from-amber-500 to-amber-300"
              : "bg-gradient-to-r from-muted-foreground/40 to-muted-foreground/20"
            }`}
          style={{ width: `${Math.min(100, (score / 10) * 100)}%` }}
        />
      </div>
    </div>
  );
}
