"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "./Reveal";
import { cn } from "@/lib/utils";
import { ConfidenceDonut } from "@/components/report/ConfidenceDonut";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
} from "lucide-react";

const EXAMPLE_REPORT = {
  title: "Market Entry Decision",
  verdict: "Proceed with a narrow pilot",
  confidence: 0.78,
  keyFindings: [
    "Demand appears plausible, but channel risk remains high.",
    "Models disagree most on pricing and timing.",
    "A limited pilot reduces downside while preserving learning speed.",
  ],
  risks: [
    { item: "Weak distribution signal", severity: "high" },
    { item: "Unclear willingness to pay", severity: "medium" },
    { item: "Execution bandwidth", severity: "medium" },
  ],
  nextActions: [
    { action: "Interview 10 target users", timing: "Now", priority: "now" },
    { action: "Test a pricing page", timing: "Next", priority: "next" },
    { action: "Expand to a second segment", timing: "Later", priority: "later" },
  ],
};

type Tab = "verdict" | "risks" | "actions";

export function ExampleReportPreview() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<Tab>("verdict");

  const tabs: { key: Tab; label: string }[] = [
    { key: "verdict", label: "Verdict" },
    { key: "risks", label: "Risks" },
    { key: "actions", label: "Next Actions" },
  ];

  return (
    <section
      className="py-16 md:py-24"
      aria-labelledby="example-report-heading"
    >
      <Reveal>
        <div className="mb-12 text-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            {t("landing.exampleReport.subtitle")}
          </p>
          <h2
            id="example-report-heading"
            className="text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
          >
            {t("landing.exampleReport.title")}
          </h2>
        </div>
      </Reveal>

      <Reveal delay={100}>
        <div className="mx-auto max-w-3xl">
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
            {/* Report header */}
            <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="flex items-center justify-between">
                <div>
                  <span className="mb-1 inline-block rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                    Example
                  </span>
                  <h3 className="mt-1 text-lg font-bold text-slate-900 dark:text-white">
                    {EXAMPLE_REPORT.title}
                  </h3>
                </div>
                <ConfidenceDonut
                  confidence={EXAMPLE_REPORT.confidence}
                  size={64}
                  label="Confidence"
                />
              </div>
            </div>

            {/* Tab bar */}
            <div className="flex border-b border-slate-200 dark:border-slate-700">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    "flex-1 px-4 py-3 text-sm font-semibold transition-colors",
                    activeTab === tab.key
                      ? "border-b-2 border-amber-500 text-amber-700 dark:text-amber-400"
                      : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="p-6">
              {activeTab === "verdict" && (
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">
                        {EXAMPLE_REPORT.verdict}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {EXAMPLE_REPORT.keyFindings.map((finding, i) => (
                      <p
                        key={i}
                        className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-400"
                      >
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                        {finding}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "risks" && (
                <div className="space-y-3">
                  {EXAMPLE_REPORT.risks.map((risk, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/40"
                    >
                      <AlertTriangle
                        className={cn(
                          "h-4 w-4 shrink-0",
                          risk.severity === "high"
                            ? "text-red-500"
                            : "text-amber-500"
                        )}
                      />
                      <span className="text-sm text-slate-700 dark:text-slate-300">
                        {risk.item}
                      </span>
                      <span
                        className={cn(
                          "ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                          risk.severity === "high"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                        )}
                      >
                        {risk.severity}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === "actions" && (
                <div className="space-y-3">
                  {EXAMPLE_REPORT.nextActions.map((action, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/40"
                    >
                      {action.priority === "now" ? (
                        <ArrowRight className="h-4 w-4 shrink-0 text-emerald-500" />
                      ) : (
                        <Clock className="h-4 w-4 shrink-0 text-slate-400" />
                      )}
                      <span className="text-sm text-slate-700 dark:text-slate-300">
                        {action.action}
                      </span>
                      <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-600 dark:bg-slate-700 dark:text-slate-400">
                        {action.timing}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
