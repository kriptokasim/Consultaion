"use client"

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

type AnimatedCounterProps = {
  value: number;
  durationMs?: number;
  className?: string;
  format?: (n: number) => string;
};

export function AnimatedCounter({ value, durationMs = 900, className, format }: AnimatedCounterProps) {
  const [display, setDisplay] = useState(0);
  const prefersReducedMotion = useReducedMotion();
  const rafRef = useRef<number | undefined>(undefined);
  const startRef = useRef<number | null>(null);
  const startValueRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion) {
      setDisplay(value);
      return;
    }

    const step = (timestamp: number) => {
      if (startRef.current === null) {
        startRef.current = timestamp;
        startValueRef.current = display;
      }

      const progress = Math.min((timestamp - startRef.current) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const nextValue = Math.round(startValueRef.current + (value - startValueRef.current) * eased);
      setDisplay(nextValue);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };

    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      startRef.current = null;
    };
  }, [value, durationMs, prefersReducedMotion]);

  return <span className={cn("tabular-nums", className)}>{format ? format(display) : display.toLocaleString()}</span>;
}

export default AnimatedCounter;
