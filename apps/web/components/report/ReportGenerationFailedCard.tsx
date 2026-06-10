import React from "react";
import { AlertTriangle, ShieldAlert, FileText, CheckCircle } from "lucide-react";

interface ReportGenerationFailedCardProps {
  reason?: string;
}

export function ReportGenerationFailedCard({ reason }: ReportGenerationFailedCardProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-zinc-900/90 to-zinc-950 p-6 shadow-2xl backdrop-blur-md md:p-8">
      {/* Decorative ambient background blur */}
      <div className="absolute -right-16 -top-16 h-36 w-36 rounded-full bg-amber-500/10 blur-3xl" />
      <div className="absolute -left-16 -bottom-16 h-36 w-36 rounded-full bg-amber-600/10 blur-3xl" />

      <div className="flex flex-col items-start gap-4 sm:flex-row sm:gap-6">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20">
          <AlertTriangle className="h-6 w-6" />
        </div>

        <div className="flex-1 space-y-4">
          <div>
            <h3 className="text-lg font-semibold tracking-tight text-amber-200 sm:text-xl">
              Decision Report Validation Guard Triggered
            </h3>
            <p className="mt-1 text-sm leading-relaxed text-zinc-400">
              To guarantee data integrity, the synthesis report rendering has been halted.
              The generated structured payload failed our strict formatting and safety rules (e.g. contains raw JSON code fences, truncated brackets, or schema leakage).
            </p>
          </div>

          {reason && (
            <div className="rounded-lg border border-amber-500/10 bg-amber-500/5 p-3.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-400 block mb-1">
                Validation Details:
              </span>
              <code className="text-xs font-mono text-zinc-300 break-words leading-relaxed">
                {reason}
              </code>
            </div>
          )}

          <div className="grid gap-3 pt-2 text-xs text-zinc-400 sm:grid-cols-2">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-500/70 shrink-0" />
              <span>Fail-closed guard activated</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-500/70 shrink-0" />
              <span>Source answers preserved below</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
