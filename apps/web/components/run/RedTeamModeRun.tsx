"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/apiClient";
import { StatusPill } from "@/components/ui/StatusPill";
import type { UiRunStatus } from "@/lib/runStatusUi";
import { useI18n } from "@/lib/i18n/client";

type RiskIssue = {
  lens: string;
  title: string;
  severity: "high" | "medium" | "low";
  description: string;
  remediation: string;
};

type RedTeamSession = {
  id: string;
  proposal_text: string;
  lenses: string[];
  status: "processing" | "completed" | "failed";
  issues: RiskIssue[];
  error?: string | null;
  created_at: string;
};

const LENSES = [
  ["security", "workspace.redteam.security"],
  ["scaling", "workspace.redteam.scaling"],
  ["compliance", "workspace.redteam.compliance"],
  ["financial", "workspace.redteam.financial"],
  ["operations", "workspace.redteam.operations"],
] as const;

export default function RedTeamModeRun({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const [session, setSession] = useState<RedTeamSession | null>(null);
  const [severity, setSeverity] = useState<string | null>(null);
  const [lens, setLens] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const load = async () => {
      try {
        const data = await apiRequest<RedTeamSession>({ path: `/redteam/${sessionId}` });
        if (cancelled) return;
        setSession(data);
        if (data.status === "processing") timer = setTimeout(load, 1800);
      } catch (err) {
        if (!cancelled) {
          setSession((current) =>
            current
              ? { ...current, status: "failed", error: err instanceof Error ? err.message : t("workspace.aux.loadError") }
              : current,
          );
          timer = setTimeout(load, 2500);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, t]);

  const filtered = useMemo(
    () =>
      session?.issues.filter((issue) =>
        (!severity || issue.severity === severity) && (!lens || issue.lens === lens),
      ) ?? [],
    [session, severity, lens],
  );

  if (!session) {
    return <div className="new-ux-aux__loading">{t("workspace.aux.loading")}</div>;
  }

  const uiStatus: UiRunStatus =
    session.status === "failed" ? "failed" : session.status === "completed" ? "closed" : "live";

  const counts = Object.fromEntries(
    LENSES.map(([id]) => [
      id,
      {
        high: session.issues.filter((issue) => issue.lens === id && issue.severity === "high").length,
        medium: session.issues.filter((issue) => issue.lens === id && issue.severity === "medium").length,
        low: session.issues.filter((issue) => issue.lens === id && issue.severity === "low").length,
      },
    ]),
  ) as Record<string, { high: number; medium: number; low: number }>;

  return (
    <div className="new-ux-aux">
      <div className="new-ux-aux__header">
        <div>
          <p className="new-ux__kicker">{t("mode.redteam.name")}</p>
          <h2>{t("workspace.redteam.title")}</h2>
          <p className="new-ux__model-copy">{session.proposal_text}</p>
        </div>
        <StatusPill status={uiStatus} />
      </div>

      {session.error && <div className="new-ux__error" role="alert">{session.error}</div>}

      {session.status === "processing" && (
        <div className="new-ux-aux__progress">{t("workspace.redteam.running")}</div>
      )}

      <div className="new-ux-aux__matrix">
        <div className="new-ux-aux__matrix-head">
          <span>{t("workspace.redteam.lens")}</span>
          <span>HIGH</span><span>MED</span><span>LOW</span>
        </div>
        {session.lenses.map((id) => (
          <div key={id} className="new-ux-aux__matrix-row">
            <button type="button" onClick={() => setLens(lens === id ? null : id)}>
              {t(LENSES.find(([key]) => key === id)?.[1] ?? id)}
            </button>
            <button type="button" disabled={!counts[id]?.high} onClick={() => { setLens(id); setSeverity("high"); }}>{counts[id]?.high ?? 0}</button>
            <button type="button" disabled={!counts[id]?.medium} onClick={() => { setLens(id); setSeverity("medium"); }}>{counts[id]?.medium ?? 0}</button>
            <button type="button" disabled={!counts[id]?.low} onClick={() => { setLens(id); setSeverity("low"); }}>{counts[id]?.low ?? 0}</button>
          </div>
        ))}
      </div>

      <section className="new-ux__section">
        <div className="new-ux-aux__section-head">
          <p className="new-ux__section-title">{t("workspace.redteam.issues")} · {filtered.length}</p>
          {(severity || lens) && (
            <button type="button" className="new-ux__nav-link" onClick={() => { setSeverity(null); setLens(null); }}>
              {t("workspace.redteam.clearFilters")}
            </button>
          )}
        </div>
        <div className="new-ux-aux__issues">
          {filtered.map((issue, index) => (
            <article key={`${issue.lens}-${index}`} className="new-ux-aux__issue">
              <div className="new-ux-aux__issue-meta">
                <span>{t(LENSES.find(([id]) => id === issue.lens)?.[1] ?? issue.lens)}</span>
                <strong data-severity={issue.severity}>{issue.severity}</strong>
              </div>
              <h3>{issue.title}</h3>
              <p>{issue.description}</p>
              <div className="new-ux-aux__remediation">
                <span>{t("workspace.redteam.remediation")}</span>
                <p>{issue.remediation}</p>
              </div>
            </article>
          ))}
          {filtered.length === 0 && <div className="new-ux-aux__empty">{t("workspace.redteam.noIssues")}</div>}
        </div>
      </section>
    </div>
  );
}
