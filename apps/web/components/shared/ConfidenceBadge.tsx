"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Sparkles } from "lucide-react";

interface ConfidenceBadgeProps {
  confidence: number; // expected between 0 and 1 (or 0 and 100)
  className?: string;
  showIcon?: boolean;
}

export default function ConfidenceBadge({
  confidence,
  className,
  showIcon = true,
}: ConfidenceBadgeProps) {
  // Normalize value to a 0-100 percentage
  const value = confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence);

  let themeClasses = "";
  if (value >= 80) {
    themeClasses = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  } else if (value >= 50) {
    themeClasses = "bg-amber-500/10 text-amber-400 border-amber-500/30";
  } else {
    themeClasses = "bg-rose-500/10 text-rose-400 border-rose-500/30";
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold backdrop-blur-sm transition-all duration-300",
        themeClasses,
        className
      )}
    >
      {showIcon && <Sparkles className="h-3 w-3 animate-pulse" />}
      <span>{value}% Confidence</span>
    </div>
  );
}
