"use client";

import React from "react";
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
}

const modes: ModeOption[] = [
  {
    id: "arena",
    label: "Arena Mode",
    description: "Disagreement-first parallel responses & claim matching",
    icon: Swords,
    gradient: "from-rose-500/10 to-pink-500/10 hover:from-rose-500/20 hover:to-pink-500/20 text-rose-400",
    borderHover: "hover:border-rose-500/50",
  },
  {
    id: "debate",
    label: "Debate Mode",
    description: "Multi-agent argument trees & position drift tracking",
    icon: Users,
    gradient: "from-blue-500/10 to-cyan-500/10 hover:from-blue-500/20 hover:to-cyan-500/20 text-blue-400",
    borderHover: "hover:border-blue-500/50",
  },
  {
    id: "voting",
    label: "Voting Mode",
    description: "Participatory prediction locks & ELO leaderboard metrics",
    icon: Vote,
    gradient: "from-amber-500/10 to-orange-500/10 hover:from-amber-500/20 hover:to-orange-500/20 text-amber-400",
    borderHover: "hover:border-amber-500/50",
  },
  {
    id: "redteam",
    label: "Red Team Mode",
    description: "Model vulnerability auditing & multi-lens stress testing",
    icon: Skull,
    gradient: "from-red-500/10 to-purple-500/10 hover:from-red-500/20 hover:to-purple-500/20 text-red-400",
    borderHover: "hover:border-red-500/50",
  },
  {
    id: "oracle",
    label: "Oracle Mode",
    description: "Step-by-step reasoning pipelines & interactive branching",
    icon: Eye,
    gradient: "from-violet-500/10 to-indigo-500/10 hover:from-violet-500/20 hover:to-indigo-500/20 text-violet-400",
    borderHover: "hover:border-violet-500/50",
  },
  {
    id: "challenge",
    label: "Challenge Mode",
    description: "Synthesis pushback, rebuttals & interactive revisions",
    icon: BrainCircuit,
    gradient: "from-emerald-500/10 to-teal-500/10 hover:from-emerald-500/20 hover:to-teal-500/20 text-emerald-400",
    borderHover: "hover:border-emerald-500/50",
  },
];

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
  return (
    <div className={cn("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4", className)}>
      {modes.map((mode) => {
        const Icon = mode.icon;
        const isActive = selectedMode === mode.id;

        return (
          <button
            key={mode.id}
            onClick={() => onChange(mode.id)}
            className={cn(
              "group relative flex flex-col items-start p-5 rounded-2xl border text-left transition-all duration-300",
              "bg-slate-900/40 backdrop-blur-md",
              isActive
                ? "border-amber-500/80 shadow-[0_0_20px_rgba(245,158,11,0.15)] ring-1 ring-amber-500/50"
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
              <h3 className="font-bold text-slate-100 group-hover:text-white text-base">
                {mode.label}
              </h3>
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
