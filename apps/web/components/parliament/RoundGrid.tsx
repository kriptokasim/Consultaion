"use client";

import React, { useEffect, useState, useMemo } from "react";
import type { DebateEvent } from "./types";
import { groupDebateRounds } from "./groupDebateRounds";
import RoundCard from "./RoundCard";
import RoundNavigator from "./RoundNavigator";

interface RoundGridProps {
  events: DebateEvent[];
}

export default function RoundGrid({ events }: RoundGridProps) {
  const { rounds, uniquePersonas } = useMemo(() => groupDebateRounds(events), [events]);
  const [activeRound, setActiveRound] = useState<number | undefined>(undefined);

  // Set initial active round
  useEffect(() => {
    if (rounds.length > 0 && activeRound === undefined) {
      setActiveRound(rounds[0].roundNumber);
    }
  }, [rounds, activeRound]);

  // Track active round via IntersectionObserver as the user scrolls
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const roundNumber = parseInt(entry.target.getAttribute("data-round-num") || "", 10);
            if (!isNaN(roundNumber)) {
              setActiveRound(roundNumber);
            }
          }
        });
      },
      {
        // Highlight when round header is in the upper part of the viewport
        rootMargin: "-120px 0px -70% 0px",
      }
    );

    const elements = document.querySelectorAll("[data-round-num]");
    elements.forEach((el) => observer.observe(el));

    return () => {
      elements.forEach((el) => observer.unobserve(el));
    };
  }, [rounds]);

  if (rounds.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/80 p-6 text-center text-sm text-stone-500 dark:border-stone-800 dark:bg-stone-950/30">
        No deliberation rounds have been recorded yet.
      </p>
    );
  }

  const gridColsClass = (() => {
    const count = uniquePersonas.length;
    if (count <= 1) return "grid-cols-1";
    if (count === 2) return "grid-cols-1 md:grid-cols-2";
    if (count === 3) return "grid-cols-1 md:grid-cols-3";
    return "grid-cols-1 md:grid-cols-2 lg:grid-cols-4";
  })();

  const roundNumbers = rounds.map((r) => r.roundNumber);

  return (
    <div className="space-y-6">
      {/* Sticky pill navigator to jump between rounds */}
      <RoundNavigator
        rounds={roundNumbers}
        activeRound={activeRound}
      />

      <div className="space-y-12">
        {rounds.map((round) => (
          <section
            key={round.roundNumber}
            id={`round-section-${round.roundNumber}`}
            data-round-num={round.roundNumber}
            className="space-y-4 scroll-mt-28"
          >
            {/* Round Title */}
            <div className="flex items-center gap-3 border-b border-stone-200/60 pb-2 dark:border-stone-800">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">
                {round.roundNumber}
              </span>
              <h3 className="text-base font-bold text-stone-900 dark:text-foreground">
                Round {round.roundNumber} Deliberation
              </h3>
            </div>

            {/* Speeches Grid */}
            <div className={`grid ${gridColsClass} gap-4`}>
              {uniquePersonas.map((personaName) => {
                const speech = round.speeches.find((s) => s.persona === personaName);
                return (
                  <RoundCard
                    key={`${round.roundNumber}-${personaName}`}
                    speech={speech}
                    personaName={personaName}
                  />
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
