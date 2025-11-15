'use client';

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { Info, Scale, ThumbsDown, ThumbsUp, Users, Trophy } from "lucide-react";
import type { JudgeVoteFlow, Member, ScoreItem } from "./types";
import { cn } from "@/lib/utils";

interface VotingChamberProps {
  scores: ScoreItem[];
  members?: Member[];
  threshold?: number;
  flows?: JudgeVoteFlow[];
  basis?: "pairwise" | "threshold";
  onComplete?: () => void;
}

const fallbackColors = ["#2563eb", "#0891b2", "#16a34a", "#b45309", "#7c3aed"];

export default function VotingChamber({
  scores,
  members,
  threshold = 7,
  flows,
  basis = "threshold",
  onComplete,
}: VotingChamberProps) {
  const roster = useMemo(() => {
    if (members?.length && members.length >= scores.length) {
      return members.map((member, index) => ({
        name: member.name,
        vote: (scores[index]?.score ?? 0) >= threshold ? "aye" : "nay",
        color: fallbackColors[index % fallbackColors.length],
      }));
    }
    return scores.map((score, index) => ({
      name: score.persona,
      vote: score.score >= threshold ? "aye" : "nay",
      color: fallbackColors[index % fallbackColors.length],
    }));
  }, [members, scores, threshold]);

  const [phase, setPhase] = useState<"intro" | "voting" | "results">("intro");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [ayeVotes, setAyeVotes] = useState<typeof roster>([]);
  const [nayVotes, setNayVotes] = useState<typeof roster>([]);

  useEffect(() => {
    if (phase !== "intro") return;
    const timer = setTimeout(() => setPhase("voting"), 1800);
    return () => clearTimeout(timer);
  }, [phase]);

  useEffect(() => {
    if (phase !== "voting" || currentIndex >= roster.length) {
      if (phase === "voting" && currentIndex >= roster.length) {
        setPhase("results");
        onComplete?.();
      }
      return;
    }

    const timer = setTimeout(() => {
      const current = roster[currentIndex];
      if (current.vote === "aye") {
        setAyeVotes((prev) => [...prev, current]);
      } else {
        setNayVotes((prev) => [...prev, current]);
      }
      setCurrentIndex((value) => value + 1);
    }, 700);
    return () => clearTimeout(timer);
  }, [phase, currentIndex, roster, onComplete]);

  const totalVotes = ayeVotes.length + nayVotes.length;
  const ayePct = totalVotes ? (ayeVotes.length / totalVotes) * 100 : 0;
  const nayPct = totalVotes ? (nayVotes.length / totalVotes) * 100 : 0;
  const winner = ayeVotes.length >= nayVotes.length ? "aye" : "nay";
  const flowPreview = useMemo(() => flows?.slice(0, 6) ?? [], [flows]);
  const [showDetails, setShowDetails] = useState(false);
  const margin = Math.abs(ayeVotes.length - nayVotes.length);

  return (
    <section className="space-y-8 rounded-3xl border border-stone-200 bg-gradient-to-br from-stone-50 via-white to-amber-50 p-6 shadow-[0_35px_65px_rgba(120,113,108,0.15)]">
      <header className="text-center space-y-2">
        <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white/80 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
          <Scale className="h-4 w-4" />
          Division chamber
        </div>
        <h1 className="text-3xl font-semibold text-stone-900">Voting Simulation</h1>
        <p className="flex items-center justify-center gap-2 text-sm text-stone-500">
          <Info className="h-4 w-4 text-amber-600" />
          {basis === "pairwise"
            ? "Derived from pairwise judge outcomes."
            : `Scores above ${threshold.toFixed(1)} march through the Aye lobby.`}
        </p>
        {phase === "results" ? (
          <p className="text-sm font-semibold text-stone-700">
            Current outcome:{" "}
            <span className="text-amber-800">
              {winner === "aye" ? "The Ayes have it" : "The Nays have it"}
            </span>
          </p>
        ) : null}
      </header>

      <div className="rounded-2xl border border-stone-200 bg-white/80 p-6 shadow-inner">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Current majority</p>
            <p className="text-2xl font-semibold text-stone-900">
              {winner === "aye" ? "The Ayes have it" : "The Nays have it"}
            </p>
            <p className="text-sm text-stone-600">
              Margin: {margin} vote{margin === 1 ? "" : "s"}
            </p>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-full border border-stone-200 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-stone-700 shadow-sm hover:border-amber-200 hover:text-amber-700"
            onClick={() => setShowDetails((value) => !value)}
            aria-pressed={showDetails}
          >
            {showDetails ? "Hide breakdown" : "Show detailed breakdown"}
          </button>
        </div>
      </div>

      {showDetails ? (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <VotePanel
              title="Aye lobby"
              icon={<ThumbsUp className="h-6 w-6 text-green-600" />}
              count={ayeVotes.length}
              percentage={ayePct}
              accent="from-green-500 to-green-300"
              description={`${ayeVotes.length} members marched through the Aye lobby`}
            />
            <VotePanel
              title="Nay lobby"
              icon={<ThumbsDown className="h-6 w-6 text-red-600" />}
              count={nayVotes.length}
              percentage={nayPct}
              accent="from-red-500 to-red-300"
              description={`${nayVotes.length} members marched through the Nay lobby`}
            />
          </div>

          <div className="grid gap-6 rounded-2xl border border-stone-200 bg-white/80 p-6 shadow-inner lg:grid-cols-2">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
                <Users className="h-4 w-4 text-amber-500" />
                Members marching
              </div>
              <div className="grid grid-cols-3 gap-4">
                {roster.map((member, index) => (
                  <AvatarCard
                    key={`${member.name}-${index}`}
                    member={member}
                    animate={phase === "voting"}
                    index={index}
                  />
                ))}
              </div>
            </div>
            <div className="space-y-4">
              <div className="rounded-2xl border border-amber-100 bg-amber-50/80 p-6 shadow-inner">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  <Trophy className="h-4 w-4" />
                  Division outcome
                </div>
                <div className="mt-4 space-y-3">
                  {phase === "results" ? (
                    <>
                      <p className="text-2xl font-semibold text-stone-900">
                        {winner === "aye" ? "The Ayes have it" : "The Nays have it"}
                      </p>
                      <p className="text-sm text-stone-600">
                        Margin: {margin} vote{margin === 1 ? "" : "s"}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-stone-600">
                      {phase === "intro"
                        ? "Division bell sounding..."
                        : "Members are still positioning inside the lobbies."}
                    </p>
                  )}
                </div>
              </div>
              {flowPreview.length ? (
                <div className="rounded-2xl border border-stone-200 bg-white/80 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Judge ledger</p>
                  <div className="mt-2 space-y-2 text-sm text-stone-700">
                    {flowPreview.map((flow) => (
                      <div key={`${flow.judge}-${flow.persona}`} className="flex items-center justify-between">
                        <span>
                          {flow.judge} → <span className="font-semibold">{flow.persona}</span>
                        </span>
                        <span
                          className={cn(
                            "text-xs font-semibold",
                            flow.vote === "aye" ? "text-emerald-700" : "text-rose-700",
                          )}
                        >
                          {flow.vote === "aye" ? "Aye" : "Nay"} ({flow.score.toFixed(1)})
                        </span>
                      </div>
                    ))}
                  </div>
                  {flows && flows.length > flowPreview.length ? (
                    <p className="mt-2 text-xs text-stone-500">
                      +{flows.length - flowPreview.length} more judge
                      {flows.length - flowPreview.length === 1 ? "" : "s"} recorded
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

const VotePanel = memo(function VotePanel({
  title,
  icon,
  count,
  percentage,
  accent,
  description,
}: {
  title: string;
  icon: React.ReactNode;
  count: number;
  percentage: number;
  accent: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/80 p-6 shadow-inner">
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            {title}
          </p>
          <p className="text-sm text-stone-500">{description}</p>
        </div>
      </div>
      <div className="mt-4 flex items-baseline gap-3">
        <span className="text-5xl font-semibold text-stone-900">{count}</span>
        <span className="text-sm text-stone-500">{percentage.toFixed(1)}%</span>
      </div>
      <div className="mt-4 h-2 rounded-full bg-stone-100">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${accent}`}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
    </div>
  );
});

const AvatarCard = memo(function AvatarCard({
  member,
  animate,
  index,
}: {
  member: { name: string; vote: string; color: string };
  animate: boolean;
  index: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!animate || !ref.current) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    const animation = ref.current.animate(
      [
        { transform: "translateY(0px)", opacity: 1 },
        { transform: "translateY(-6px)", opacity: 0.9 },
        { transform: "translateY(0px)", opacity: 1 },
      ],
      {
        duration: 700,
        delay: index * 60,
        easing: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    );
    return () => animation.cancel();
  }, [animate, index]);

  return (
    <div className="text-center text-sm text-stone-600">
      <div
        ref={ref}
        className="mx-auto flex h-14 w-14 items-center justify-center rounded-full text-base font-semibold text-white shadow-lg"
        style={{ background: member.color }}
        aria-label={`${member.name} voted ${member.vote}`}
      >
        {member.name.charAt(0)}
      </div>
      <p className="mt-2 font-medium text-stone-800">{member.name}</p>
      <p className="text-xs uppercase tracking-wide text-stone-400">{member.vote}</p>
    </div>
  );
});
