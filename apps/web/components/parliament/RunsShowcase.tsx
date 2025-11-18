"use client";

import Link from "next/link";
import { useMemo } from "react";
import { FileText, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import StatusBadge from "@/components/parliament/StatusBadge";
import { cn } from "@/lib/utils";

export type RunSummary = {
  id: string;
  prompt: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type RunsShowcaseProps = {
  runs: RunSummary[];
};

const pillTone: Record<string, string> = {
  running: "bg-amber-100 text-amber-800 border-amber-200",
  completed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  queued: "bg-amber-50 text-amber-800 border-amber-100",
  error: "bg-rose-100 text-rose-800 border-rose-200",
};

export default function RunsShowcase({ runs }: RunsShowcaseProps) {
  const visibleRuns = useMemo(() => runs.slice(0, 8), [runs]);

  if (!visibleRuns.length) return null;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {visibleRuns.map((run, idx) => (
        <article
          key={run.id}
          className="group relative overflow-hidden rounded-2xl border border-amber-200/70 bg-gradient-to-br from-amber-50/70 via-white to-amber-50/50 p-5 shadow-[0_18px_40px_rgba(112,73,28,0.12)] transition duration-200 hover:-translate-y-[3px] hover:shadow-[0_26px_50px_rgba(112,73,28,0.18)] dark:border-amber-900/50 dark:from-stone-900 dark:via-stone-900 dark:to-amber-900/20"
          style={{ transitionDelay: `${Math.min(idx, 4) * 40}ms` }}
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-amber-100/20 via-transparent to-amber-50/10 opacity-0 transition duration-300 group-hover:opacity-100 dark:from-amber-900/10 dark:to-amber-900/5" />
          <header className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-amber-200/80 bg-white/80 text-amber-700 shadow-inner shadow-amber-900/5 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
                <FileText className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700 dark:text-amber-200">
                  Run
                </p>
                <p className="text-sm font-semibold text-amber-900 dark:text-amber-100 line-clamp-1">
                  {run.id}
                </p>
              </div>
            </div>
            <StatusBadge status={run.status} className={cn("border", pillTone[run.status] || "bg-amber-50 text-amber-800 border-amber-100")} />
          </header>
          <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-stone-800 dark:text-amber-50/80">{run.prompt}</p>
          <div className="mt-4 flex items-center justify-between text-xs text-stone-600 dark:text-amber-100/70">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" aria-hidden="true" />
              <span>Updated {new Date(run.updated_at ?? run.created_at).toLocaleString()}</span>
            </div>
            <span className="rounded-full border border-amber-200/70 bg-white/80 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/30 dark:bg-amber-950/30 dark:text-amber-100">
              Status: {run.status || "queued"}
            </span>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Button asChild size="sm" className="rounded-lg">
              <Link href={`/runs/${run.id}`} aria-label={`View run ${run.id}`}>
                View
              </Link>
            </Button>
            <Button asChild variant="ghost" size="sm" className="gap-1 text-amber-800 dark:text-amber-100">
              <Link href={`/runs/${run.id}?export=1`} aria-label={`Export run ${run.id}`}>
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Export
              </Link>
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}
