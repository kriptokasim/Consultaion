"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface RevealProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  direction?: "up" | "down" | "left" | "right" | "none";
}

/**
 * Fades content in as it scrolls into view — without ever hiding it first.
 *
 * The previous implementation initialised to `opacity-0` and only revealed
 * after an IntersectionObserver callback plus a timeout. Since every landing
 * section (the <h1> included) is wrapped in this component, the server-rendered
 * HTML painted a background and nothing readable: the page stayed blank until
 * the JS chunk had loaded, parsed and hydrated, and stayed blank permanently if
 * it failed to load at all.
 *
 * The resting state is now visible. Only content that is already below the fold
 * when the effect runs is armed for animation, so nothing on screen can flash
 * out, and a viewer with no JavaScript gets the whole page.
 */
export function Reveal({
  children,
  delay = 0,
  className,
  direction = "up",
}: RevealProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [phase, setPhase] = useState<"resting" | "armed" | "revealed">(
    "resting"
  );

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced) {
      setPhase("revealed");
      return;
    }

    // Already on screen: leave it painted rather than hiding it to animate it
    // back in. This is what keeps the hero out of the animation path entirely.
    if (node.getBoundingClientRect().top < window.innerHeight) {
      setPhase("revealed");
      return;
    }

    setPhase("armed");

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          window.setTimeout(() => setPhase("revealed"), delay);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [delay]);

  const hidden = phase === "armed";

  const translateClass = {
    up: hidden ? "translate-y-6" : "translate-y-0",
    down: hidden ? "-translate-y-6" : "translate-y-0",
    left: hidden ? "translate-x-6" : "translate-x-0",
    right: hidden ? "-translate-x-6" : "translate-x-0",
    none: "",
  }[direction];

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-700 ease-out",
        hidden ? "opacity-0" : "opacity-100",
        translateClass,
        className
      )}
    >
      {children}
    </div>
  );
}
