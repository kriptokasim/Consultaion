"use client";

import React, { useEffect, useRef } from "react";
import anime from "animejs";

export const RosettaClock: React.FC = () => {
  const hourRef = useRef<SVGLineElement | null>(null);
  const minuteRef = useRef<SVGLineElement | null>(null);
  const secondRef = useRef<SVGLineElement | null>(null);

  useEffect(() => {
    const updateHands = () => {
      const now = new Date();
      const seconds = now.getSeconds();
      const minutes = now.getMinutes();
      const hours = now.getHours() % 12;

      const secDeg = seconds * 6;
      const minDeg = minutes * 6 + seconds * 0.1;
      const hourDeg = hours * 30 + minutes * 0.5;

      if (secondRef.current) {
        anime({
          targets: secondRef.current,
          rotate: secDeg,
          duration: 250,
          easing: "linear",
        });
      }
      if (minuteRef.current) {
        anime({
          targets: minuteRef.current,
          rotate: minDeg,
          duration: 400,
          easing: "easeOutQuad",
        });
      }
      if (hourRef.current) {
        anime({
          targets: hourRef.current,
          rotate: hourDeg,
          duration: 600,
          easing: "easeOutQuad",
        });
      }
    };

    updateHands();
    const interval = setInterval(updateHands, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="inline-flex items-center gap-2">
      <svg viewBox="0 0 40 40" className="h-8 w-8 text-amber-900 dark:text-amber-100">
        <circle
          cx="20"
          cy="20"
          r="18"
          className="fill-amber-50/80 stroke-amber-700 dark:fill-stone-900 dark:stroke-amber-200"
          strokeWidth={1.5}
        />
        {[0, 90, 180, 270].map((deg) => (
          <line
            key={deg}
            x1="20"
            y1="4"
            x2="20"
            y2="7"
            stroke="currentColor"
            strokeWidth={1.2}
            transform={`rotate(${deg} 20 20)`}
            strokeLinecap="round"
          />
        ))}
        <line
          ref={hourRef}
          x1="20"
          y1="20"
          x2="20"
          y2="11"
          stroke="currentColor"
          strokeWidth={1.6}
          strokeLinecap="round"
          transform="rotate(0 20 20)"
        />
        <line
          ref={minuteRef}
          x1="20"
          y1="20"
          x2="20"
          y2="8"
          stroke="currentColor"
          strokeWidth={1.2}
          strokeLinecap="round"
          transform="rotate(0 20 20)"
        />
        <line
          ref={secondRef}
          x1="20"
          y1="20"
          x2="20"
          y2="6"
          stroke="#dc2626"
          strokeWidth={0.9}
          strokeLinecap="round"
          transform="rotate(0 20 20)"
        />
        <circle cx="20" cy="20" r="1.2" fill="currentColor" />
      </svg>
      <span className="hidden text-xs font-serif uppercase tracking-wide text-amber-700 dark:text-amber-200 sm:inline">
        Rosetta Chamber
      </span>
    </div>
  );
};
