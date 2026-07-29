"use client";

import {
  CheckCircle2,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  Sparkles,
} from "lucide-react";
import SafeMarkdown from "@/components/content/SafeMarkdown";
import {
  DecisionReportView,
  type DecisionReport,
} from "@/components/report/DecisionReportView";
import { useI18n } from "@/lib/i18n/client";
import type { SynthesisStreamingState } from "@/lib/workspace/synthesisReducer";

interface LiveSynthesisCardProps {
  state: SynthesisStreamingState;
}

const verificationBadge: Record<
  string,
  { label: string; icon: typeof ShieldCheck; className: string }
> = {
  verified: {
    label: "Verified",
    icon: ShieldCheck,
    className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  },
  unverified: {
    label: "Unverified",
    icon: ShieldQuestion,
    className: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
  failed: {
    label: "Failed",
    icon: ShieldAlert,
    className: "bg-destructive/10 text-destructive",
  },
  unavailable: {
    label: "Not checked",
    icon: ShieldQuestion,
    className: "bg-muted text-muted-foreground",
  },
};

export function LiveSynthesisCard({ state }: LiveSynthesisCardProps) {
  const { t } = useI18n();
  const isFinal = state.status === "final";
  const isFailed = state.status === "failed";
  const isStreaming = state.status === "streaming";
  const report =
    state.report &&
    typeof state.report === "object" &&
    !Array.isArray(state.report)
      ? (state.report as DecisionReport)
      : null;
  const countParams = {
    successful: state.successfulCount,
    total: state.totalCount,
  };
  const statusLabel = isFinal
    ? t("arena.synthesis.final", countParams)
    : isFailed
      ? t("arena.synthesis.failed")
      : isStreaming
        ? t("arena.synthesis.drafting", countParams)
        : t("arena.synthesis.draft", countParams);
  const vs = state.verificationStatus || "unavailable";
  const VB = verificationBadge[vs] || verificationBadge.unavailable;

  return (
    <article
      className="min-w-0 overflow-hidden rounded-2xl border border-primary/25 bg-card shadow-sm"
      aria-busy={isStreaming}
      data-testid="live-synthesis-card"
    >
      <header className="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b border-border bg-primary/[0.04] px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2">
          <Sparkles
            className="h-4 w-4 shrink-0 text-primary"
            aria-hidden="true"
          />
          <h3 className="truncate text-sm font-semibold">
            {t("arena.synthesis.title")}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {state.verificationStatus && (
            <span
              className={`inline-flex min-h-6 items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${VB.className}`}
              title={`Verification: ${VB.label}`}
            >
              <VB.icon className="h-3 w-3" aria-hidden="true" />
              {VB.label}
            </span>
          )}
          <span
            className={`inline-flex min-h-8 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              isFinal
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : isFailed
                  ? "bg-destructive/10 text-destructive"
                  : "bg-amber-500/10 text-amber-700 dark:text-amber-300"
            }`}
            aria-live="polite"
            aria-atomic="true"
          >
            {isStreaming ? (
              <Loader2
                className="h-3.5 w-3.5 motion-safe:animate-spin"
                aria-hidden="true"
              />
            ) : isFinal ? (
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            ) : null}
            {statusLabel}
          </span>
        </div>
      </header>

      <div className="min-w-0 p-4 sm:p-5">
        {isFinal && report ? (
          <DecisionReportView
            report={report}
            rawSynthesis={state.text}
            variant="arena"
            synthesisStatus="succeeded"
          />
        ) : state.text ? (
          <SafeMarkdown
            content={state.text}
            className="break-words [overflow-wrap:anywhere]"
          />
        ) : isFailed ? (
          <p className="text-sm text-destructive">
            {t("arena.synthesis.failed")}
          </p>
        ) : (
          <div
            className="space-y-3"
            aria-label={t("arena.synthesis.preparing")}
          >
            <p className="text-sm text-muted-foreground">
              {t("arena.synthesis.preparing")}
            </p>
            <div className="h-4 w-full rounded bg-muted/60 motion-safe:animate-pulse" />
            <div className="h-4 w-4/5 rounded bg-muted/60 motion-safe:animate-pulse" />
          </div>
        )}

        {!isFinal && !isFailed && (
          <p className="mt-4 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
            {t("arena.synthesis.lateResponses")}
          </p>
        )}
      </div>
    </article>
  );
}
