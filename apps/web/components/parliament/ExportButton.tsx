"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/toast";
import { API_ORIGIN } from "@/lib/config/runtime";

type ExportButtonProps = {
  debateId: string;
  apiBase?: string;
  onBillingLimit?: (code?: string) => void;
};

export default function ExportButton({ debateId, apiBase, onBillingLimit }: ExportButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = apiBase || API_ORIGIN;
  const { pushToast } = useToast();

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/debates/${debateId}/export`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        if (response.status === 402 && onBillingLimit) {
          const detail = (await response.json().catch(() => null)) as any;
          onBillingLimit(detail?.detail?.code || detail?.code);
          setBusy(false);
          return;
        }
        const text = (await response.text().catch(() => "")) || response.statusText;
        throw new Error(text || "Export failed");
      }
      const blob = await response.blob();
      const contentDisposition = response.headers.get("content-disposition");
      const fallbackName = `${debateId}.md`;
      const filename =
        contentDisposition?.split("filename=")[1]?.replace(/"/g, "") || fallbackName;
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 2000);
      pushToast({ title: "Markdown export ready", variant: "success" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export");
      console.error("Export failed", err);
      pushToast({ title: "Export failed", description: "We could not prepare the markdown file.", variant: "error" });
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
