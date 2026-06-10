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
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  const elapsedRemainder = elapsedSeconds % 60;

  return (
    <section className="rounded-3xl border border-stone-200 bg-white px-6 py-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        <StatusPill status={status} />
        <div className="flex flex-wrap gap-4 text-sm text-stone-600">
          {debateId && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">Run ID</p>
              {runUrl ? (
                <a
                  href={runUrl}
                  className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
                >
                  {debateId}
                </a>
              ) : (
                <button
                  type="button"
                  onClick={onCopy}
                  className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700"
                >
                  {debateId}
                </button>
              )}
            </div>
          )}
          {status !== "idle" && status !== "creating" && status !== "created" && status !== "redirecting" && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">Elapsed</p>
              <p className="text-sm font-semibold text-stone-800">
                {elapsedMinutes.toString().padStart(2, "0")}:
                {elapsedRemainder.toString().padStart(2, "0")}
              </p>
            </div>
          )}
          {(status === "running" || status === "streaming" || status === "synthesis_pending") && (
            <div>
              <p className="text-xs uppercase tracking-wide text-stone-400">Active Model</p>
              <p className="text-sm font-semibold text-stone-800">
                {activePersona ?? "Contacting models"}
              </p>
            </div>
          )}
        </div>
      </div>
      {status === "idle" && (
        <p className="mt-3 text-xs text-stone-600">
          Arena is idle. Enter a prompt and click <strong>Run Arena</strong> to compare models.
        </p>
      )}
      {status === "recoverable_error" && (
        <p className="mt-3 text-xs text-amber-600">
          Connection interrupted — retrying automatically. You can safely leave this page.
        </p>
      )}
      {status === "terminal_error" && (
        <p className="mt-3 text-xs text-red-600">
          Run encountered a terminal error. Check the details below.
        </p>
      )}
    </section>
  );
}
