"use client";

import { useState } from "react";
import { ArrowUpRight, Lightbulb, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

type Suggestion = {
  title: string;
  description: string;
  prompt: string;
};

type PromptSuggestionsProps = {
  suggestions?: Suggestion[];
  onSelect?: (prompt: string) => void;
  heading?: string;
};

const DEFAULT_SUGGESTIONS: Suggestion[] = [
  {
    title: "Policy clarity",
    description: "Ask the chamber to draft a crisp, multi-stakeholder policy.",
    prompt: "Draft a national data governance policy that balances AI innovation with privacy protections.",
  },
  {
    title: "Risk & safety",
    description: "Stress-test an idea across failure modes and mitigations.",
    prompt: "Evaluate safety risks of deploying AI copilots to clinicians and propose governance guardrails.",
  },
  {
    title: "Debate a trade-off",
    description: "Invite competing voices to weigh pros and cons.",
    prompt: "Should governments subsidize foundation models for public services? Provide a 3-point debate.",
  },
  {
    title: "Product guidance",
    description: "Shape a feature with measurable outcomes.",
    prompt: "Design a launch plan for a command-palette smart search inside a developer IDE.",
  },
];

export default function PromptSuggestions({
  onSelect,
  suggestions = DEFAULT_SUGGESTIONS,
  heading = "Prompt suggestions",
}: PromptSuggestionsProps) {
  const [activePrompt, setActivePrompt] = useState<string | null>(null);

  const handleSelect = (prompt: string) => {
    setActivePrompt(prompt);
    onSelect?.(prompt);
    if (!onSelect && typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(prompt).catch(() => {});
    }
  };

  return (
    <div className="rounded-2xl border border-amber-200/70 bg-white/85 p-4 shadow-[0_16px_40px_rgba(112,73,28,0.12)] backdrop-blur-sm dark:border-amber-900/40 dark:bg-stone-900/70">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-amber-800 shadow-inner shadow-amber-900/5 dark:bg-amber-900/40 dark:text-amber-100">
            <Lightbulb className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">{heading}</p>
            <p className="text-xs text-amber-900/80 dark:text-amber-100/70">Click to prefill or copy a starting point.</p>
          </div>
        </div>
        <Sparkles className="h-4 w-4 text-amber-500" aria-hidden="true" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {suggestions.map((item) => (
          <button
            key={item.prompt}
            type="button"
            onClick={() => handleSelect(item.prompt)}
            className={cn(
              "group relative flex h-full flex-col items-start gap-2 rounded-xl border bg-gradient-to-br from-amber-50/90 via-white to-amber-50/60 px-4 py-3 text-left shadow-sm transition duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white hover:-translate-y-[2px] hover:shadow-lg dark:from-stone-900 dark:via-stone-900 dark:to-amber-900/20 dark:text-amber-50",
              activePrompt === item.prompt ? "border-amber-400 shadow-amber-200/60" : "border-amber-100/80 hover:border-amber-300",
            )}
          >
            <div className="flex w-full items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">{item.title}</p>
                <p className="text-xs text-stone-600 dark:text-amber-100/70">{item.description}</p>
              </div>
              <ArrowUpRight className="h-4 w-4 text-amber-500 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
            </div>
            <p className="text-sm text-stone-700 dark:text-amber-50/80">{item.prompt}</p>
            {activePrompt === item.prompt ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner dark:bg-amber-900/40 dark:text-amber-100">
                Prefilled
              </span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
