"use client";

import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "./Reveal";
import { cn } from "@/lib/utils";
import {
  X,
  Check,
  Copy,
  GitCompareArrows,
  FileText,
  Shield,
  BarChart3,
  Target,
} from "lucide-react";

const comparisonPoints = [
  {
    manual: "Copy-paste between tabs",
    consultaion: "Structured parallel comparison",
    manualIcon: Copy,
    consultaionIcon: GitCompareArrows,
  },
  {
    manual: "You spot differences manually",
    consultaion: "Disagreement surfaced automatically",
    manualIcon: Copy,
    consultaionIcon: BarChart3,
  },
  {
    manual: "Raw chat text output",
    consultaion: "Structured decision report",
    manualIcon: Copy,
    consultaionIcon: FileText,
  },
  {
    manual: "No history or sharing",
    consultaion: "Shareable audit trail",
    manualIcon: Copy,
    consultaionIcon: Shield,
  },
  {
    manual: "Prompt-engineering variance",
    consultaion: "Consistent scoring and formatting",
    manualIcon: Copy,
    consultaionIcon: BarChart3,
  },
  {
    manual: "More reading, same confusion",
    consultaion: "Clear verdict with next actions",
    manualIcon: Copy,
    consultaionIcon: Target,
  },
];

export function DifferentiationSection() {
  const { t } = useI18n();

  return (
    <section
      className="py-16 md:py-24"
      aria-labelledby="differentiation-heading"
    >
      <Reveal>
        <div className="mb-12 text-center">
          <h2
            id="differentiation-heading"
            className="text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
          >
            {t("landing.differentiation.title")}
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600 dark:text-slate-400">
            {t("landing.differentiation.subtitle")}
          </p>
        </div>
      </Reveal>

      <div className="mx-auto max-w-3xl">
        {/* Column headers */}
        <Reveal delay={50}>
          <div className="mb-4 grid grid-cols-2 gap-4 px-2">
            <div className="text-center">
              <span className="inline-block rounded-full bg-slate-100 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                Manual copy-paste
              </span>
            </div>
            <div className="text-center">
              <span className="inline-block rounded-full bg-amber-100 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                Consultaion
              </span>
            </div>
          </div>
        </Reveal>

        {/* Comparison rows */}
        <div className="space-y-3">
          {comparisonPoints.map((point, index) => (
            <Reveal key={index} delay={index * 60}>
              <div className="grid grid-cols-2 gap-4">
                {/* Manual side */}
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white/60 p-4 dark:border-slate-800 dark:bg-slate-900/40">
                  <X className="h-4 w-4 shrink-0 text-slate-400" />
                  <span className="text-sm text-slate-500 dark:text-slate-400">
                    {point.manual}
                  </span>
                </div>

                {/* Consultaion side */}
                <div className="flex items-center gap-3 rounded-xl border border-amber-200/60 bg-amber-50/40 p-4 dark:border-amber-800/30 dark:bg-amber-950/20">
                  <Check className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {point.consultaion}
                  </span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
