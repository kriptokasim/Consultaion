"use client";

import { useI18n } from "@/lib/i18n/client";

import StatusPill from "./StatusPill";
import type { ArenaRunUiState } from "./StatusPill";

interface SessionHUDProps {
  status: ArenaRunUiState;
  debateId?: string | null;
  elapsedSeconds?: number;
  activePersona?: string;
  onCopy?: () => void;
  runUrl?: string | null;
}

export default function SessionHUD({
  status,
  debateId,
  elapsedSeconds = 0,
  activePersona,
  onCopy,
  runUrl,
}: SessionHUDProps) {
  const { t } = useI18n();
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  const elapsedRemainder = elapsedSeconds % 60;

  return (
    <section className="rounded-3xl border border-stone-200 bg-white px-6 py-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        <StatusPill status={status} />
        <div className="flex flex-wrap gap-4 text-sm text-stone-600">
          {debateId && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">{t("live.session.runId")}</p>
              {runUrl ? (
                <a
                  href={runUrl}
                  aria-label={t("live.session.openRun", { id: debateId })}
                  className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
                >
                  {debateId}
                </a>
              ) : (
                <button
                  type="button"
                  onClick={onCopy}
                  aria-label={t("live.session.copyRunId")}
                  className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700"
                >
                  {debateId}
                </button>
              )}
            </div>
          )}
          {status !== "idle" && status !== "creating" && status !== "created" && status !== "redirecting" && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">{t("live.session.elapsed")}</p>
              <p className="text-sm font-semibold text-stone-800">
                {elapsedMinutes.toString().padStart(2, "0")}:
                {elapsedRemainder.toString().padStart(2, "0")}
              </p>
            </div>
          )}
          {(status === "running" || status === "streaming" || status === "synthesis_pending") && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">{t("live.session.activeModel")}</p>
              <p className="text-sm font-semibold text-stone-800">
                {activePersona ?? t("live.session.contactingModels")}
              </p>
            </div>
          )}
        </div>
      </div>
      {status === "idle" && (
        <p className="mt-3 text-xs text-stone-600">
          {t("live.session.idleHelp")}
        </p>
      )}
      {status === "recoverable_error" && (
        <p className="mt-3 text-xs text-amber-600">
          {t("live.session.recoverableError")}
        </p>
      )}
      {status === "terminal_error" && (
        <p className="mt-3 text-xs text-red-600">
          {t("live.session.terminalError")}
        </p>
      )}
    </section>
  );
}
