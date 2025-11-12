"use client";

import { useState } from "react";

type ExportButtonProps = {
  debateId: string;
  apiBase?: string;
};

export default function ExportButton({ debateId, apiBase }: ExportButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = apiBase || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/debates/${debateId}/export`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("Export failed");
      }
      const data = await response.json();
      const url = `${base}${data.uri}`;
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleExport}
        disabled={busy}
        className="inline-flex w-full items-center justify-center rounded border border-white/20 bg-transparent px-4 py-2 text-sm font-semibold text-white text-center transition hover:bg-white/10 disabled:opacity-50"
        aria-busy={busy}
        aria-label="Export debate as Markdown"
      >
        {busy ? "Preparing…" : "Export Markdown"}
      </button>
      {error ? <p className="text-xs text-red-400">{error}</p> : null}
    </div>
  );
}
