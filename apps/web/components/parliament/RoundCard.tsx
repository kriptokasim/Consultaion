"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatModelLabel } from "@/lib/ui/formatters";
import { sanitizeMarkdown } from "@/lib/sanitize";
import { cn } from "@/lib/utils";
import type { RoundSpeech } from "./groupDebateRounds";

interface RoundCardProps {
  speech?: RoundSpeech;
  personaName: string;
}

export default function RoundCard({ speech, personaName }: RoundCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // If no speech exists for this persona in this round, render a placeholder card
  if (!speech) {
    return (
      <Card className="flex flex-col justify-center items-center p-6 min-h-[160px] border border-dashed border-stone-200 bg-stone-50/50 text-center dark:border-stone-800 dark:bg-stone-950/30">
        <p className="text-xs italic text-stone-400 dark:text-stone-600">
          No statement recorded from {personaName} this round.
        </p>
      </Card>
    );
  }

  const { speechText, role, provider } = speech;
  const providerLabel = formatModelLabel(provider);
  const isLongText = speechText.length > 350;

  return (
    <Card className="group relative flex flex-col justify-between border border-stone-200 bg-white/80 p-5 shadow-sm transition hover:shadow-md dark:border-stone-800 dark:bg-card/85">
      <div className="space-y-4">
        {/* Header: Persona & Role */}
        <div className="flex items-start justify-between gap-2 border-b border-stone-100 pb-3 dark:border-stone-800">
          <div>
            <h4 className="text-sm font-semibold text-stone-900 dark:text-foreground">
              {personaName}
            </h4>
            {providerLabel && (
              <p className="text-[0.68rem] text-stone-400 dark:text-stone-500">
                {providerLabel}
              </p>
            )}
          </div>
          <Badge
            className={cn(
              "text-[0.65rem] font-semibold tracking-wider uppercase px-2 py-0.5 border shadow-none",
              role === "critic"
                ? "bg-purple-50 text-purple-700 border-purple-100 dark:bg-purple-950/30 dark:text-purple-300 dark:border-purple-800"
                : "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800"
            )}
          >
            {role}
          </Badge>
        </div>

        {/* Content with optional clamping and fade-out */}
        <div className="relative">
          <div
            className={cn(
              "prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed text-stone-800 dark:text-foreground/90 transition-all duration-300",
              !isExpanded && isLongText && "line-clamp-[8] overflow-hidden max-h-[200px]"
            )}
            dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(speechText) }}
          />
          {!isExpanded && isLongText && (
            <div 
              className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-white via-white/80 to-transparent pointer-events-none dark:from-stone-950 dark:via-stone-950/80" 
              aria-hidden="true"
            />
          )}
        </div>
      </div>

      {/* Toggle Button */}
      {isLongText && (
        <div className="mt-4 pt-2 border-t border-stone-100/50 dark:border-stone-800/50 flex justify-end">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs font-semibold text-amber-700 hover:text-amber-800 focus:outline-none dark:text-amber-500 dark:hover:text-amber-400 transition"
          >
            {isExpanded ? "Show less" : "Show more"}
          </button>
        </div>
      )}
    </Card>
  );
}
