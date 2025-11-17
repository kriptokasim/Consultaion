"use client";

import React, { useEffect, useRef } from "react";
import anime from "animejs";

interface ChampionGlowProps {
  active: boolean;
  children: React.ReactNode;
}

export const ChampionGlow: React.FC<ChampionGlowProps> = ({ active, children }) => {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || !active) return;
    const el = ref.current;

    const timeline = anime.timeline({
      easing: "easeOutQuad",
    });

    timeline
      .add({
        targets: el,
        scale: [1, 1.03],
        boxShadow: ["0 0 0 rgba(251, 191, 36, 0.0)", "0 0 30px rgba(251, 191, 36, 0.45)"],
        duration: 450,
      })
      .add({
        targets: el,
        scale: 1,
        boxShadow: "0 0 0 rgba(251, 191, 36, 0.0)",
        duration: 500,
      });

    return () => {
      anime.remove(el);
    };
  }, [active]);

  return (
    <div
      ref={ref}
      className="relative rounded-2xl border border-amber-400/60 bg-amber-50/80 p-4 shadow-sm dark:border-amber-300/70 dark:bg-amber-900/30"
    >
      <div className="pointer-events-none absolute -inset-px rounded-2xl border border-amber-400/40 blur-[0.5px]" />
      {children}
    </div>
  );
};
