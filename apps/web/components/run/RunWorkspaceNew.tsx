"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, startDebate } from "@/lib/api";
import { apiRequest } from "@/lib/apiClient";
import { defaultPanelConfig } from "@/lib/panels";
import { useModelRegistry } from "@/lib/api/hooks/useModelRegistry";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { useRunWorkspace } from "@/hooks/useRunWorkspace";
import { getMode, MODES, type ModeId } from "@/lib/modes";
import { toUiRunStatus, type UiRunStatus } from "@/lib/runStatusUi";
import { useI18n } from "@/lib/i18n/client";
import { PrimaryNav } from "@/components/navigation/PrimaryNav";
import { PanelPicker, type PanelPickerModel } from "@/components/ui/PanelPicker";
import { StatusPill } from "@/components/ui/StatusPill";
import { DecisionReport } from "@/components/report/DecisionReport";
import type { DecisionReport as DecisionReportData } from "@/components/report/DecisionReportView";
import OracleModeRun from "@/components/run/OracleModeRun";
import RedTeamModeRun from "@/components/run/RedTeamModeRun";

type LiveRowState = "queued" | "streaming" | "complete" | "failed";

type AuxiliaryRun =
  | { kind: "oracle"; id: string }
  | { kind: "redteam"; id: string }
  | null;

const REDTEAM_LENSES = [
  { id: "security", labelKey: "workspace.redteam.security" },
  { id: "scaling", labelKey: "workspace.redteam.scaling" },
  { id: "compliance", labelKey: "workspace.redteam.compliance" },
  { id: "financial", labelKey: "workspace.redteam.financial" },
  { id: "operations", labelKey: "workspace.redteam.operations" },
] as const;

const MODEL_STATE_LABEL_KEYS: Record<LiveRowState, string> = {
  queued: "workspace.modelState.queued",
  streaming: "workspace.modelState.streaming",
  complete: "workspace.modelState.complete",
  failed: "status.failed",
};

function reportFromState(synthesisState: any, debate: any): Record<string, any> | null {
  if (synthesisState?.report && typeof synthesisState.report === "object") {
    return synthesisState.report as Record<string, any>;
  }
  const persisted = debate?.final_meta?.report;
  return persisted && typeof persisted === "object" ? (persisted as Record<string, any>) : null;
}

export default function RunWorkspaceNew({
  initialRunId = null,
  initialAuxRun = null,
}: {
  initialRunId?: string | null;
  initialAuxRun?: AuxiliaryRun;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [runId, setRunId] = useState<string | null>(initialRunId);
  const [auxRun, setAuxRun] = useState<AuxiliaryRun>(initialAuxRun);
  const [question, setQuestion] = useState("");
  const [modeId, setModeId] = useState<ModeId>("arena");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [selectedRiskLenses, setSelectedRiskLenses] = useState<string[]>(["security", "scaling", "compliance"]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mode = getMode(modeId);
  const activeModeNameKey = auxRun?.kind === "oracle" ? "mode.oracle.name" : auxRun?.kind === "redteam" ? "mode.redteam.name" : mode.nameKey;
  const workspace = useRunWorkspace(runId);

  useEffect(() => {
    const persistedMode = workspace.debate?.mode;
    if (!runId || !persistedMode) return;
    if (MODES.some((item) => item.id === persistedMode)) {
      setModeId(persistedMode as ModeId);
    }
  }, [runId, workspace.debate?.mode]);

  // R9: the real model registry (GET /models), not a hardcoded list.
  const modelsQuery = useModelRegistry();
  const registryModels = useMemo(
    () => (modelsQuery.data?.models ?? []).filter((item) => item.enabled),
    [modelsQuery.data],
  );
  const pickerModels = useMemo<PanelPickerModel[]>(
    () => registryModels.map((item) => ({ id: item.id, name: item.display_name, provider: item.provider })),
    [registryModels],
  );

  // Seed a default panel once the registry loads; never overrides a choice the user already made.
  useEffect(() => {
    if (selectedModelIds.length > 0 || registryModels.length === 0) return;
    setSelectedModelIds(registryModels.slice(0, Math.min(4, mode.panelSize[1])).map((item) => item.id));
  }, [registryModels, selectedModelIds.length, mode.panelSize]);

  // PS05: real runs for the "returning user" state — pinned active run + recent
  // runs below the composer. Silently empty for a genuine first-time/anonymous
  // visitor (401/no history); never fabricated example content.
  const recentRunsQuery = useDebatesList({ limit: 6 });
  const recentRuns = useMemo(() => {
    const items = recentRunsQuery.data?.items ?? [];
    return items.map((item) => {
      const modeKnown = MODES.some((candidate) => candidate.id === item.mode);
      return {
        id: item.id,
        prompt: item.prompt,
        modeLabel: modeKnown ? t(getMode(item.mode).nameKey) : item.mode || "",
        uiStatus: toUiRunStatus(item.status, { hasReport: Boolean(item.verdict) }) as UiRunStatus,
        confidence:
          typeof item.verdict?.confidence === "number" ? Math.round(item.verdict.confidence * 100) : undefined,
      };
    });
  }, [recentRunsQuery.data, t]);

  const pinnedRun = useMemo(
    () => recentRuns.find((run) => run.uiStatus === "live" || run.uiStatus === "needsYou") ?? null,
    [recentRuns],
  );
  const otherRecentRuns = useMemo(
    () => recentRuns.filter((run) => run.id !== pinnedRun?.id),
    [recentRuns, pinnedRun],
  );

  const report = useMemo(
    () => reportFromState(workspace.synthesisState, workspace.debate),
    [workspace.synthesisState, workspace.debate],
  );

  const visibleModels = useMemo(() => {
    const selected = new Set(selectedModelIds);
    return pickerModels.filter((model) => selected.has(model.id));
  }, [selectedModelIds, pickerModels]);

  // The workspace hook already merges live stream buffers with persisted responses.
  // Consume that canonical projection rather than rebuilding it from raw events.
  const liveRows = useMemo(() => {
    const rows = new Map<string, { modelId: string; name: string; text: string; state: LiveRowState }>();
    for (const model of visibleModels) {
      rows.set(model.id, { modelId: model.id, name: model.name, text: "", state: "queued" });
    }
    for (const response of workspace.mergedStreamingResponses) {
      const modelId = response.modelId;
      const matching = pickerModels.find((model) => model.id === modelId);
      const state: LiveRowState =
        response.state === "failed" ? "failed" :
        response.state === "completed" ? "complete" :
        "streaming";
      rows.set(modelId, {
        modelId,
        name: response.displayName || matching?.name || modelId,
        text: response.content || "",
        state,
      });
    }
    return Array.from(rows.values());
  }, [workspace.mergedStreamingResponses, visibleModels, pickerModels]);

  const handleModeChange = (next: ModeId) => {
    setModeId(next);
    const nextMode = getMode(next);
    setSelectedModelIds((current) => {
      if (registryModels.length === 0) return current;
      if (nextMode.panelSize[1] === 1) return [current[0] || registryModels[0].id];
      if (current.length >= nextMode.panelSize[0]) return current;
      return registryModels.slice(0, nextMode.panelSize[0]).map((item) => item.id);
    });
  };

  const toggleModel = (id: string) => {
    setSelectedModelIds((current) => {
      const next = current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id];
      if (next.length < mode.panelSize[0] || next.length > mode.panelSize[1]) return current;
      return next;
    });
  };

  const handleSend = async () => {
    const trimmed = question.trim();
    if (!trimmed || sending) return;

    if (modeId === "redteam") {
      if (trimmed.length < 10) {
        setError(t("workspace.redteam.validationProposal"));
        return;
      }
      if (selectedRiskLenses.length === 0) {
        setError(t("workspace.redteam.validationLens"));
        return;
      }
    } else if (modeId !== "oracle" && selectedModelIds.length < mode.panelSize[0]) {
      setError(
        t(
          mode.panelSize[0] === 1
            ? "workspace.composer.selectMinimumOne"
            : "workspace.composer.selectMinimumMany",
          { count: mode.panelSize[0] },
        ),
      );
      return;
    }

    setSending(true);
    setError(null);

    try {
      if (modeId === "oracle") {
        const result = await apiRequest<{ session_id: string }>({
          method: "POST",
          path: "/oracle",
          body: { prompt: trimmed },
        });
        setRunId(null);
        setAuxRun({ kind: "oracle", id: result.session_id });
        router.replace("/new?oracle=" + encodeURIComponent(result.session_id));
        return;
      }

      if (modeId === "redteam") {
        const result = await apiRequest<{ id: string }>({
          method: "POST",
          path: "/redteam",
          body: {
            proposal_text: trimmed,
            lenses: selectedRiskLenses,
          },
        });
        setRunId(null);
        setAuxRun({ kind: "redteam", id: result.id });
        router.replace("/new?redteam=" + encodeURIComponent(result.id));
        return;
      }

      const base = defaultPanelConfig();
      const seats = selectedModelIds.map((id) => {
        const model = registryModels.find((item) => item.id === id);
        return {
          seat_id: id,
          display_name: model?.display_name || id,
          provider_key: model?.provider || "unknown",
          model: id,
          role_profile: "architect",
        };
      });

      const result = await startDebate({
        prompt: trimmed,
        panel_config: { ...base, seats },
        mode: modeId,
        compare_models: modeId === "compare" ? selectedModelIds : undefined,
        gateway_policy: "auto",
      });

      setAuxRun(null);
      setRunId(result.id);
      router.replace("/new?run=" + encodeURIComponent(result.id));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError(t("workspace.composer.signInRequired"));
      } else if (err instanceof Error) {
        setError(err.message || t("workspace.composer.startError"));
      } else {
        setError(t("workspace.composer.startError"));
      }
    } finally {
      setSending(false);
    }
  };

  const hasDebateRun = Boolean(runId && workspace.debate);
  const hasAuxRun = Boolean(auxRun);
  const hasRun = hasDebateRun || hasAuxRun;
  const uiStatus = toUiRunStatus(workspace.debate?.status || workspace.status, {
    hasReport: Boolean(report),
    hasError: Boolean(workspace.error),
  });

  return (
    <div className="new-ux" data-surface="ink">
      <div className="new-ux__shell">
        <header className="new-ux__header">
          <div className="new-ux__brand">Consultaion</div>
          <PrimaryNav variant="inline" />
          {hasRun && <span className="new-ux__meta">{t(activeModeNameKey)}</span>}
        </header>

        <main className="new-ux__main">
          {!hasRun ? (
            <section className="new-ux__hero">
              <p className="new-ux__kicker">{t("workspace.hero.kicker")}</p>
              <h1>{t("workspace.hero.title")}</h1>
              <p className="new-ux__lede">{t("workspace.hero.lede")}</p>

              {pinnedRun && (
                <div className="new-ux-pinned-run" role="status">
                  <StatusPill status={pinnedRun.uiStatus} />
                  <p className="new-ux-pinned-run__question">{pinnedRun.prompt}</p>
                  <Link href={`/new?run=${pinnedRun.id}`} className="new-ux__secondary">
                    {t("workspace.recent.rejoin")}
                  </Link>
                </div>
              )}

              <div className="new-ux__composer">
                <div className="new-ux__mode-row" role="group" aria-label={t("workspace.composer.modeGroupLabel")}>
                  {MODES.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="new-ux__mode"
                      aria-pressed={item.id === modeId}
                      onClick={() => handleModeChange(item.id)}
                    >
                      {t(item.nameKey)}
                    </button>
                  ))}
                </div>
                <p className="new-ux__mode-blurb">{t(mode.blurbKey)}</p>

                <label className="new-ux__label" htmlFor="new-ux-question">{t("workspace.composer.questionLabel")}</label>
                <textarea
                  id="new-ux-question"
                  className="new-ux__input"
                  rows={4}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={t("workspace.composer.questionPlaceholder")}
                />

                {modeId === "oracle" ? (
                  <div className="new-ux__mode-note">{t("workspace.oracle.composerNote")}</div>
                ) : modeId === "redteam" ? (
                  <div className="new-ux__choice-group" role="group" aria-label={t("workspace.redteam.lens")}>
                    <div className="new-ux__choice-head">
                      <span className="new-ux__section-title">{t("workspace.redteam.lens")}</span>
                      <span className="new-ux__choice-count">{selectedRiskLenses.length}</span>
                    </div>
                    <div className="new-ux__choice-grid">
                      {REDTEAM_LENSES.map((item) => {
                        const selected = selectedRiskLenses.includes(item.id);
                        return (
                          <button
                            key={item.id}
                            type="button"
                            className="new-ux__choice"
                            data-selected={selected}
                            aria-pressed={selected}
                            onClick={() =>
                              setSelectedRiskLenses((current) =>
                                selected ? current.filter((value) => value !== item.id) : [...current, item.id],
                              )
                            }
                          >
                            {t(item.labelKey)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <PanelPicker
                    models={pickerModels}
                    selectedIds={selectedModelIds}
                    onToggle={toggleModel}
                    minModels={mode.panelSize[0]}
                    maxModels={mode.panelSize[1]}
                    isLoading={modelsQuery.isLoading}
                    error={modelsQuery.error instanceof Error ? modelsQuery.error.message : null}
                  />
                )}
              </div>

              {error && <div className="new-ux__error" role="alert">{error}</div>}

              {otherRecentRuns.length > 0 && (
                <div className="new-ux__section">
                  <p className="new-ux__section-title">{t("workspace.recent.title")}</p>
                  {otherRecentRuns.map((run) => (
                    <div key={run.id} className="new-ux-recent__row">
                      <div className="new-ux-recent__row-head">
                        <button
                          type="button"
                          className="new-ux-recent__question"
                          onClick={() => setQuestion(run.prompt)}
                        >
                          {run.prompt}
                        </button>
                        <StatusPill status={run.uiStatus} />
                      </div>
                      <p className="new-ux-recent__meta">
                        {run.modeLabel}
                        {typeof run.confidence === "number" ? ` · ${run.confidence}%` : ""}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ) : auxRun?.kind === "oracle" ? (
            <section className="new-ux__run">
              <OracleModeRun sessionId={auxRun.id} />
            </section>
          ) : auxRun?.kind === "redteam" ? (
            <section className="new-ux__run">
              <RedTeamModeRun sessionId={auxRun.id} />
            </section>
          ) : (
            <section className="new-ux__run">
              <div className="new-ux__desktop-run">
                <div>
                  <p className="new-ux__kicker">
                    {t(mode.nameKey)} <StatusPill status={uiStatus} />
                  </p>
                  <h1 className="new-ux__question">{workspace.debate?.prompt || question}</h1>

                  <div className="new-ux__section">
                    <p className="new-ux__section-title">{t("workspace.composer.panelLabel")}</p>
                    {liveRows.map((row) => (
                      <article key={row.modelId} className="new-ux__model">
                        <div className="new-ux__model-head">
                          <span className="new-ux__model-name">{row.name}</span>
                          <span className="new-ux__model-state">{t(MODEL_STATE_LABEL_KEYS[row.state])}</span>
                        </div>
                        {row.text && <p className="new-ux__model-copy">{row.text}</p>}
                      </article>
                    ))}
                  </div>

                  {modeId !== "compare" && (
                    <div className="new-ux__divergence">
                      <p className="new-ux__section-title">{t("workspace.run.divergenceTitle")}</p>
                      <p className="new-ux__model-copy">{t("workspace.run.divergencePlaceholder")}</p>
                    </div>
                  )}
                </div>

                <div className="new-ux__verdict">
                  <div className="new-ux__verdict-top">
                    <span>
                      {modeId === "compare"
                        ? t("workspace.run.compareResults")
                        : workspace.synthesisState.status === "final"
                          ? t("workspace.run.verdict")
                          : t("workspace.run.verdictForming")}
                    </span>
                    <span>{workspace.isPollingFallback ? t("workspace.run.polling") : workspace.sseStatus}</span>
                  </div>
                  {modeId === "compare" ? (
                    <div className="new-ux__compare-grid">
                      {liveRows.map((row) => (
                        <article key={row.modelId} className="new-ux__compare-card">
                          <div className="new-ux__model-head">
                            <span className="new-ux__model-name">{row.name}</span>
                            <span className="new-ux__model-state">{t(MODEL_STATE_LABEL_KEYS[row.state])}</span>
                          </div>
                          <p className="new-ux__model-copy">
                            {row.text || t("workspace.run.waitingForModel")}
                          </p>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="new-ux__verdict-grid">
                      <div>
                        <div className="new-ux__verdict-word">
                          {report?.verdict?.decision_type || (workspace.synthesisState.status === "failed" ? t("status.failed") : "—")}
                        </div>
                        <p className="new-ux__model-copy">
                          {report?.verdict?.rationale || workspace.synthesisState.text || t("workspace.run.verdictPlaceholder")}
                        </p>
                      </div>
                      <div>
                        <div className="new-ux__confidence">
                          {typeof report?.verdict?.confidence === "number"
                            ? String(Math.round(report.verdict.confidence * 100))
                            : "—"}
                        </div>
                        <div className="new-ux__smallcaps">{t("workspace.run.confidenceLabel")}</div>
                      </div>
                    </div>
                  )}

                  {modeId !== "compare" && report && (
                    <div className="new-ux__report">
                      <p className="new-ux__kicker">{t("workspace.report.title")}</p>
                      <DecisionReport run={{ report: report as DecisionReportData }} audience="brief" />
                      <Link className="new-ux__nav-link" href={"/runs/" + runId}>{t("workspace.report.openFull")}</Link>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}
        </main>
      </div>

      {!hasRun && (
        <div className="new-ux__actions">
          <div className="new-ux__actions-inner">
            <button
              type="button"
              className="new-ux__primary"
              onClick={handleSend}
              disabled={sending || !question.trim()}
            >
              {sending ? t("workspace.composer.sendBusy") : t("workspace.composer.sendIdle")}
            </button>
          </div>
        </div>
      )}

      <PrimaryNav variant="bottom-bar" />
    </div>
  );
}
