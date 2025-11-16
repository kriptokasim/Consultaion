import StatusPill from "./StatusPill";

interface SessionHUDProps {
  status: "running" | "completed" | "idle" | "error";
  debateId?: string | null;
  elapsedSeconds?: number;
  activePersona?: string;
  onCopy?: () => void;
}

export default function SessionHUD({
  status,
  debateId,
  elapsedSeconds = 0,
  activePersona,
  onCopy,
}: SessionHUDProps) {
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  const elapsedRemainder = elapsedSeconds % 60;

  return (
    <section className="rounded-3xl border border-stone-200 bg-white px-6 py-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        <StatusPill status={status} label={status === "running" ? "In session" : status} />
        <div className="flex flex-wrap gap-4 text-sm text-stone-600">
          <div>
            <p className="text-xs uppercase tracking-wide text-stone-400">Debate ID</p>
            <button
              type="button"
              disabled={!debateId}
              onClick={onCopy}
              className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 disabled:opacity-40"
            >
              {debateId ?? "N/A"}
            </button>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-stone-400">Elapsed</p>
            <p className="text-sm font-semibold text-stone-800">
              {elapsedMinutes.toString().padStart(2, "0")}:
              {elapsedRemainder.toString().padStart(2, "0")}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-stone-400">Speaker</p>
            <p className="text-sm font-semibold text-stone-800">
              {activePersona ?? "Awaiting floor"}
            </p>
          </div>
        </div>
      </div>
      {status === "idle" ? (
        <p className="mt-3 text-xs text-stone-600">
          Session is idle. Enter a prompt and <strong>Summon a Session</strong> to convene the chamber.
        </p>
      ) : null}
    </section>
  );
}
