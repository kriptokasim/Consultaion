"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/apiClient";
import { StatusPill } from "@/components/ui/StatusPill";
import type { UiRunStatus } from "@/lib/runStatusUi";
import { useI18n } from "@/lib/i18n/client";

type ReasoningNode = {
  id: string;
  title: string;
  type: "fact" | "claim" | "uncertainty" | "conclusion";
  content: string;
};

type Branch = {
  id: string;
  parent_branch_id: string | null;
  assumption_text: string;
  nodes: ReasoningNode[];
  created_at: string;
};

type OracleSession = {
  id: string;
  prompt: string;
  status: "running" | "completed" | "failed";
  branches: Branch[];
  created_at: string;
};

export default function OracleModeRun({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const [session, setSession] = useState<OracleSession | null>(null);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [forkNodeId, setForkNodeId] = useState<string | null>(null);
  const [assumption, setAssumption] = useState("");
  const [forking, setForking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const load = async () => {
      try {
        const data = await apiRequest<OracleSession>({ path: `/oracle/${sessionId}` });
        if (cancelled) return;
        setSession(data);
        if (!activeBranchId && data.branches.length) {
          const root = data.branches.find((branch) => branch.parent_branch_id === null);
          setActiveBranchId(root?.id ?? data.branches[0].id);
        }
        setError(null);
        if (data.status === "running") {
          timer = setTimeout(load, 1800);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("workspace.aux.loadError"));
          timer = setTimeout(load, 2500);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, activeBranchId, t]);

  const activeBranch = useMemo(
    () => session?.branches.find((branch) => branch.id === activeBranchId) ?? null,
    [session, activeBranchId],
  );

  const uiStatus: UiRunStatus =
    session?.status === "failed" ? "failed" : session?.status === "completed" ? "closed" : "live";

  const fork = async () => {
    if (!session || !activeBranchId || !forkNodeId || assumption.trim().length < 3 || forking) return;
    setForking(true);
    setError(null);
    try {
      await apiRequest({
        path: `/oracle/${session.id}/fork`,
        method: "POST",
        body: {
          parent_branch_id: activeBranchId,
          fork_node_id: forkNodeId,
          assumption_text: assumption.trim(),
        },
      });
      setForkNodeId(null);
      setAssumption("");
      setSession((current) => (current ? { ...current, status: "running" } : current));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("workspace.aux.forkError"));
    } finally {
      setForking(false);
    }
  };

  if (!session) {
    return <div className="new-ux-aux__loading">{t("workspace.aux.loading")}</div>;
  }

  return (
    <div className="new-ux-aux">
      <div className="new-ux-aux__header">
        <div>
          <p className="new-ux__kicker">{t("mode.oracle.name")}</p>
          <h2>{t("workspace.oracle.title")}</h2>
          <p className="new-ux__model-copy">{session.prompt}</p>
        </div>
        <StatusPill status={uiStatus} />
      </div>

      {error && <div className="new-ux__error" role="alert">{error}</div>}

      {session.status === "running" && (
        <div className="new-ux-aux__progress">
          <span>{t("workspace.oracle.running")}</span>
          <span aria-hidden="true">…</span>
        </div>
      )}

      <div className="new-ux-aux__grid">
        <aside className="new-ux-aux__sidebar">
          <p className="new-ux__section-title">{t("workspace.oracle.branches")}</p>
          <div className="new-ux-aux__branch-list">
            {session.branches.map((branch) => (
              <button
                key={branch.id}
                type="button"
                className="new-ux-aux__branch"
                data-active={branch.id === activeBranchId}
                onClick={() => {
                  setActiveBranchId(branch.id);
                  setForkNodeId(null);
                }}
              >
                <span>{branch.parent_branch_id ? t("workspace.oracle.forked") : t("workspace.oracle.root")}</span>
                <strong>{branch.assumption_text}</strong>
              </button>
            ))}
          </div>
        </aside>

        <section className="new-ux-aux__content">
          <p className="new-ux__section-title">{t("workspace.oracle.reasoningMap")}</p>
          {activeBranch?.nodes.length ? (
            <div className="new-ux-aux__nodes">
              {activeBranch.nodes.map((node) => (
                <article key={node.id} className="new-ux-aux__node">
                  <div className="new-ux-aux__node-meta">
                    <span>{node.type}</span>
                    {node.type !== "conclusion" && (
                      <button type="button" onClick={() => setForkNodeId(node.id)}>
                        {t("workspace.oracle.fork")}
                      </button>
                    )}
                  </div>
                  <h3>{node.title}</h3>
                  <p>{node.content}</p>
                  {forkNodeId === node.id && (
                    <div className="new-ux-aux__fork">
                      <label htmlFor={`fork-${node.id}`}>{t("workspace.oracle.counterAssumption")}</label>
                      <input
                        id={`fork-${node.id}`}
                        value={assumption}
                        onChange={(event) => setAssumption(event.target.value)}
                        placeholder={t("workspace.oracle.counterAssumptionPlaceholder")}
                      />
                      <div className="new-ux-aux__fork-actions">
                        <button className="new-ux__primary" type="button" disabled={forking || assumption.trim().length < 3} onClick={() => void fork()}>
                          {forking ? t("workspace.oracle.forking") : t("workspace.oracle.forkPath")}
                        </button>
                        <button className="new-ux__secondary" type="button" onClick={() => setForkNodeId(null)}>
                          {t("common.cancel")}
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="new-ux-aux__empty">{t("workspace.oracle.waiting")}</div>
          )}
        </section>
      </div>
    </div>
  );
}
