"use client";

import { useState } from "react";

type ExportCSVButtonProps = {
  debateId: string;
  apiBase?: string;
};

export default function ExportCSVButton({ debateId, apiBase }: ExportCSVButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = apiBase || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleClick = async () => {
    setBusy(true);
    setError(null);
    try {
      const url = `${base}/debates/${debateId}/scores.csv`;
      const response = await fetch(url, { method: "GET" });
      if (!response.ok) {
        throw new Error("CSV export failed");
      }
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export CSV");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className="inline-flex w-full items-center justify-center rounded border border-white/20 bg-transparent px-4 py-2 text-sm font-semibold text-white text-center transition hover:bg-white/10 disabled:opacity-50"
        aria-busy={busy}
        aria-label="Export judge scores as CSV"
      >
        {busy ? "Exporting…" : "Export CSV"}
      </button>
      {error ? <p className="text-xs text-red-400">{error}</p> : null}
    </div>
  );
}
