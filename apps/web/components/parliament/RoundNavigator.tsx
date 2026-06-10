"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface RoundNavigatorProps {
  rounds: number[];
  activeRound?: number;
  onRoundClick?: (roundNum: number) => void;
}

export default function RoundNavigator({
  rounds,
  activeRound,
  onRoundClick,
}: RoundNavigatorProps) {
  const handleJump = (roundNum: number) => {
    if (onRoundClick) {
      onRoundClick(roundNum);
    }
    const element = document.getElementById(`round-section-${roundNum}`);
    if (element) {
      // Offset scrolling slightly to account for sticky navigation
      const yOffset = -90;
      const y = element.getBoundingClientRect().top + window.scrollY + yOffset;
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  };

  if (rounds.length <= 1) {
    return null;
  }

  return (
    <nav 
      className="sticky top-14 z-20 w-full bg-stone-50/90 backdrop-blur-md border-b border-stone-200 py-3 mb-6 dark:bg-background/90 dark:border-stone-800"
      aria-label="Debate round navigation"
    >
      <div className="flex items-center gap-3 overflow-x-auto px-1 scrollbar-none">
        <span className="text-xs font-semibold uppercase tracking-wider text-stone-500 shrink-0 dark:text-stone-400">
          Jump to Round:
        </span>
        <div className="flex gap-2">
          {rounds.map((roundNum) => {
            const isActive = activeRound === roundNum;
            return (
              <button
                key={roundNum}
                type="button"
                onClick={() => handleJump(roundNum)}
                className={cn(
                  "rounded-full px-4 py-1 text-xs font-semibold transition border",
                  isActive
                    ? "bg-amber-600 text-white border-amber-600 shadow-sm"
                    : "bg-white hover:bg-stone-100 text-stone-600 border-stone-200 hover:border-stone-300 dark:bg-card dark:hover:bg-stone-800 dark:text-stone-300 dark:border-stone-800 dark:hover:border-stone-700"
                )}
                aria-label={`Scroll to Round ${roundNum}`}
              >
                R{roundNum}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
