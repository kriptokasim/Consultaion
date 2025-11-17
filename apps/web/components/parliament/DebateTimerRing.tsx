"use client";

import React, { useEffect, useRef } from "react";
import anime from "animejs";

interface DebateTimerRingProps {
  durationMs: number;
  running: boolean;
  onComplete?: () => void;
  label?: string;
}

export const DebateTimerRing: React.FC<DebateTimerRingProps> = ({
  durationMs,
  running,
  onComplete,
  label = "Debate Timer",
}) => {
  const circleRef = useRef<SVGCircleElement | null>(null);
  const textRef = useRef<HTMLSpanElement | null>(null);
  const animeRef = useRef<anime.AnimeInstance | null>(null);

  useEffect(() => {
    if (!circleRef.current) return;

    const radius = 42;
    const circumference = 2 * Math.PI * radius;

    circleRef.current.style.strokeDasharray = `${circumference}`;
    circleRef.current.style.strokeDashoffset = `${circumference}`;

    if (animeRef.current) {
      animeRef.current.pause();
      animeRef.current = null;
    }

    if (!running) return;

    const startTime = performance.now();

    animeRef.current = anime({
      targets: circleRef.current,
      strokeDashoffset: [circumference, 0],
      duration: durationMs,
      easing: "linear",
      update: () => {
        if (!textRef.current) return;
        const elapsed = performance.now() - startTime;
        const remaining = Math.max(0, durationMs - elapsed);
        const seconds = Math.round(remaining / 1000);
        textRef.current.textContent = `${seconds}s`;
      },
      complete: () => {
        if (textRef.current) textRef.current.textContent = "0s";
        if (onComplete) onComplete();
      },
    });

    return () => {
      if (animeRef.current) {
        animeRef.current.pause();
        animeRef.current = null;
      }
    };
  }, [durationMs, running, onComplete]);

  return (
    <div className="inline-flex flex-col items-center gap-2">
      <div className="relative h-24 w-24">
        <svg viewBox="0 0 100 100" className="h-full w-full" aria-hidden="true">
          <circle
            cx="50"
            cy="50"
            r="42"
            className="fill-none stroke-amber-200/40 dark:stroke-amber-900/60"
            strokeWidth={6}
          />
          <circle
            ref={circleRef}
            cx="50"
            cy="50"
            r="42"
            className="fill-none stroke-amber-600 dark:stroke-amber-300"
            strokeWidth={6}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
          />
        </svg>

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-900 text-amber-200 shadow-inner dark:bg-stone-900 dark:text-amber-200">
            <span className="text-lg font-serif">◯</span>
          </div>
        </div>
      </div>
      <span
        ref={textRef}
        className="font-mono text-xs uppercase tracking-wide text-amber-800 dark:text-amber-100"
      >
        {Math.round(durationMs / 1000)}s
      </span>
      <span className="text-[10px] uppercase tracking-wide text-amber-700/80 dark:text-amber-200/70">
        {label}
      </span>
    </div>
  );
};
