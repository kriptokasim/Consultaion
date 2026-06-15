"use client";

import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  Swords,
  Users,
  Vote,
  Skull,
  Eye,
  BrainCircuit,
  LucideIcon,
} from "lucide-react";

export type ModeType = "arena" | "debate" | "voting" | "redteam" | "oracle" | "challenge";

interface ModeOption {
  id: ModeType;
  label: string;
  description: string;
  icon: LucideIcon;
  gradient: string;
  borderHover: string;
  badge?: string;
  badgeColor?: string;
}

const ENABLE_EXPERIMENTAL = process.env.NEXT_PUBLIC_ENABLE_EXPERIMENTAL_MODES === "true";

const coreModes: ModeOption[] = [
  {
    id: "arena",
    label: "Arena",
    description: "Run your question across multiple AI models. Compare perspectives, surface disagreement, get a synthesized decision report.",
    icon: Swords,
    gradient: "from-rose-500/10 to-pink-500/10 hover:from-rose-500/20 hover:to-pink-500/20 text-rose-400",
    borderHover: "hover:border-rose-500/50",
  },
  {
    id: "debate",
    label: "Structured Debate",
    description: "Multi-agent argument trees with position tracking and moderated deliberation.",
    icon: Users,
    gradient: "from-blue-500/10 to-cyan-500/10 hover:from-blue-500/20 hover:to-cyan-500/20 text-blue-400",
    borderHover: "hover:border-blue-500/50",
    badge: "Advanced",
    badgeColor: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  },
];

const experimentalModes: ModeOption[] = ENABLE_EXPERIMENTAL ? [
  {
    id: "voting",
    label: "Voting",
    description: "Participatory prediction locks & ELO leaderboard metrics",
    icon: Vote,
    gradient: "from-amber-500/10 to-orange-500/10 hover:from-amber-500/20 hover:to-orange-500/20 text-amber-400",
    borderHover: "hover:border-amber-500/50",
    badge: "Experimental",
    badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  },
  {
    id: "redteam",
    label: "Red Team",
    description: "Model vulnerability auditing & multi-lens stress testing",
    icon: Skull,
    gradient: "from-red-500/10 to-purple-500/10 hover:from-red-500/20 hover:to-purple-500/20 text-red-400",
    borderHover: "hover:border-red-500/50",
    badge: "Experimental",
    badgeColor: "bg-red-500/10 text-red-400 border-red-500/20",
  },
  {
    id: "oracle",
    label: "Oracle",
    description: "Reasoning summary pipelines & interactive branching",
    icon: Eye,
    gradient: "from-violet-500/10 to-indigo-500/10 hover:from-violet-500/20 hover:to-indigo-500/20 text-violet-400",
    borderHover: "hover:border-violet-500/50",
    badge: "Experimental",
    badgeColor: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  },
  {
    id: "challenge",
    label: "Challenge",
    description: "Synthesis pushback, rebuttals & interactive revisions",
    icon: BrainCircuit,
    gradient: "from-emerald-500/10 to-teal-500/10 hover:from-emerald-500/20 hover:to-teal-500/20 text-emerald-400",
    borderHover: "hover:border-emerald-500/50",
    badge: "Experimental",
    badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  },
] : [];

const modes: ModeOption[] = [...coreModes, ...experimentalModes];

interface ModeSelectorProps {
  selectedMode: ModeType;
  onChange: (mode: ModeType) => void;
  className?: string;
}

export default function ModeSelector({
  selectedMode,
  onChange,
  className,
}: ModeSelectorProps) {
  const [mounted, setMounted] = useState(false);
  const prefersReducedMotion = typeof window !== "undefined"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  useEffect(() => {
    if (!prefersReducedMotion) {
      setMounted(true);
    }
  }, [prefersReducedMotion]);

  return (
    <div className={cn(
      "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
      "md:overflow-visible overflow-x-auto snap-x snap-mandatory pb-2 md:pb-0",
      className
    )}>
      {modes.map((mode, index) => {
        const Icon = mode.icon;
        const isActive = selectedMode === mode.id;

        return (
          <button
            key={mode.id}
            onClick={() => onChange(mode.id)}
            aria-pressed={isActive}
            aria-label={`Select ${mode.label} mode`}
            style={{
              animationDelay: mounted ? `${index * 60}ms` : undefined,
            }}
            className={cn(
              "group relative flex flex-col items-start p-5 rounded-2xl border text-left transition-all duration-300 min-w-[280px] md:min-w-0 snap-start",
              "bg-slate-900/40 backdrop-blur-md",
              mounted && "animate-in fade-in slide-in-from-bottom-2 fill-mode-both",
              isActive
                ? "border-amber-500/80 shadow-[0_0_20px_#f59e0b26] ring-1 ring-amber-500/50"
                : "border-slate-800 hover:bg-slate-900/60",
              mode.borderHover
            )}
          >
            {/* Background Gradient Glow on Hover */}
            <div
              className={cn(
                "absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-gradient-to-br -z-10",
                mode.gradient
              )}
            />

            <div className="flex items-center gap-3 mb-2">
              <div
                className={cn(
                  "p-2.5 rounded-xl border transition-all duration-300",
                  isActive
                    ? "bg-amber-500/20 border-amber-500/40 text-amber-400"
                    : "bg-slate-800/80 border-slate-700/80 text-slate-400 group-hover:text-amber-400 group-hover:border-amber-500/30"
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-100 group-hover:text-white text-base">
                  {mode.label}
                </h3>
                {mode.badge && (
                  <span className={cn(
                    "text-[10px] font-semibold rounded-full px-2 py-0.5 border",
                    mode.badgeColor
                  )}>
                    {mode.badge}
                  </span>
                )}
              </div>
            </div>

            <p className="text-sm text-slate-400 group-hover:text-slate-300 leading-relaxed">
              {mode.description}
            </p>

            {isActive && (
              <span className="absolute top-4 right-4 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
