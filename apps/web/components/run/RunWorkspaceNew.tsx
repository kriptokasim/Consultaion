"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, startDebate } from "@/lib/api";
import { defaultPanelConfig } from "@/lib/panels";
import { AVAILABLE_MODELS } from "@/components/arena/ModelPanelSheet";
import { useRunWorkspace } from "@/hooks/useRunWorkspace";
import { getMode, MODES, type ModeId } from "@/lib/modes";
import { toUiRunStatus, UI_RUN_STATUS_LABEL_KEYS } from "@/lib/runStatusUi";
import { useI18n } from "@/lib/i18n/client";
import type { PersistedModelResponse } from "@/lib/api/types";

type LiveRowState = "queued" | "streaming" | "complete" | "failed";

const MODEL_STATE_LABEL_KEYS: Record<LiveRowState, string> = {
  queued: "workspace.modelState.queued",
  streaming: "workspace.modelState.streaming",
  complete: "workspace.modelState.complete",
  failed: "status.failed",
};

function textFromResponse(response: PersistedModelResponse): string {
  return response.content || "";
}

function nameFromResponse(response: PersistedModelResponse): string {
  return response.display_name || response.provider || "Model";
}

function reportFromState(synthesisState: any, debate: any): Record<string, any> | null {
  if (synthesisState?.report && typeof synthesisState.report === "object") {
    return synthesisState.report as Record<string, any>;
  }
  const persisted = debate?.final_meta?.report;
  return persisted && typeof persisted === "object" ? (persisted as Record<string, any>) : null;
}

export default function RunWorkspaceNew({ initialRunId = null }: { initialRunId?: string | null }) {
  const router = useRouter();
  const { t } = useI18n();
  const [runId, setRunId] = useState<string | null>(initialRunId);
  const [question, setQuestion] = useState("");
  const [modeId, setModeId] = useState<ModeId>("arena");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(
    AVAILABLE_MODELS.slice(0, 4).map((model) => model.id),
  );
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mode = getMode(modeId);
  const workspace = useRunWorkspace(runId);

  const report = useMemo(
    () => reportFromState(workspace.synthesisState, workspace.debate),
    [workspace.synthesisState, workspace.debate],
  );

  const visibleModels = useMemo(() => {
    const selected = new Set(selectedModelIds);
    return AVAILABLE_MODELS.filter((model) => selected.has(model.id));
  }, [selectedModelIds]);

  const liveRows = useMemo(() => {
    const rows = new Map<string, { name: string; text: string; state: LiveRowState }>();

    for (const model of visibleModels) {
      rows.set(model.id, { name: model.name, text: "", state: "queued" });
    }

    for (const response of workspace.responses || []) {
      const id = String(response?.model_id || "");
      const matching = visibleModels.find((model) => model.id === id);
      const key = matching?.id || id;
      if (!key) continue;
      rows.set(key, {
        name: matching?.name || nameFromResponse(response),
        text: textFromResponse(response),
        state: response?.success === false ? "failed" : "complete",
      });
    }

    for (const event of workspace.events || []) {
      const payload = (event as any)?.payload || event;
      const eventType = String((event as any)?.type || payload?.type || "");
      if (![
        "model_response_started",
        "model_response_delta",
        "model_response_completed",
        "model_response_failed",
        "arena_response",
        "message",
        "seat_message",
      ].includes(eventType)) {
        continue;
      }
      const id = String(payload?.model_id || payload?.model || payload?.provider_model || "");
      const matching = visibleModels.find((model) => model.id === id);
      const key = matching?.id || id;
      if (!key) continue;
      const existing = rows.get(key) || { name: matching?.name || "Model", text: "", state: "streaming" as LiveRowState };
      const delta =
        typeof payload?.delta === "string"
          ? payload.delta
          : typeof payload?.text === "string"
            ? payload.text
            : typeof payload?.content === "string"
              ? payload.content
              : "";
      rows.set(key, {
        name: existing.name,
        text: delta && eventType.endsWith("_delta") ? existing.text + delta : delta || existing.text,
        state: eventType.endsWith("_failed")
          ? "failed"
          : eventType.endsWith("_completed")
            ? "complete"
            : "streaming",
      });
    }

    return Array.from(rows.values());
  }, [workspace.events, workspace.responses, visibleModels]);

  const handleModeChange = (next: ModeId) => {
    setModeId(next);
    const nextMode = getMode(next);
    setSelectedModelIds((current) => {
      if (nextMode.panelSize[1] === 1) return [current[0] || AVAILABLE_MODELS[0].id];
      if (current.length >= nextMode.panelSize[0]) return current;
      return AVAILABLE_MODELS.slice(0, nextMode.panelSize[0]).map((model) => model.id);
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

    if (selectedModelIds.length < mode.panelSize[0]) {
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
      const base = defaultPanelConfig();
      const seats = selectedModelIds.map((id) => {
        const model = AVAILABLE_MODELS.find((item) => item.id === id);
        return {
          seat_id: id,
          display_name: model?.name || id,
          provider_key: model?.providerKey || "unknown",
          model: id,
          role_profile: "architect",
        };
      });

      const result = await startDebate({
        prompt: trimmed,
        panel_config: { ...base, seats },
        mode: modeId,
        gateway_policy: "auto",
      });

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

  const hasRun = Boolean(runId && workspace.debate);
  const uiStatus = toUiRunStatus(workspace.debate?.status || workspace.status, {
    hasReport: Boolean(report),
    hasError: Boolean(workspace.error),
  });
  const currentStatusLabel = t(UI_RUN_STATUS_LABEL_KEYS[uiStatus]);

  return (
    <div className="new-ux" data-surface="ink">
      <div className="new-ux__shell">
        <header className="new-ux__header">
          <div className="new-ux__brand">Consultaion</div>
          <div className="new-ux__nav" aria-label={t("nav.mobile.label")}>
            <Link href="/new" className="new-ux__nav-link new-ux__nav-link--active">{t("nav.ask")}</Link>
            <Link href="/runs" className="new-ux__nav-link">{t("nav.runs")}</Link>
            <Link href="/settings" className="new-ux__nav-link">{t("nav.you")}</Link>
          </div>
          {hasRun && <span className="new-ux__meta">{t(mode.nameKey)}</span>}
        </header>

        <main className="new-ux__main">
          {!hasRun ? (
            <section className="new-ux__hero">
              <p className="new-ux__kicker">{t("workspace.hero.kicker")}</p>
              <h1>{t("workspace.hero.title")}</h1>
              <p className="new-ux__lede">{t("workspace.hero.lede")}</p>

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

                <div className="new-ux__panel">
                  <div className="new-ux__panel-head">
                    <span className="new-ux__meta">{t("workspace.composer.panelLabel")}</span>
                    <span className="new-ux__meta">{selectedModelIds.length} / {mode.panelSize[1]}</span>
                  </div>
                  <div className="new-ux__panel-list">
                    {AVAILABLE_MODELS.map((model) => {
                      const selected = selectedModelIds.includes(model.id);
                      return (
                        <button
                          key={model.id}
                          type="button"
                          className="new-ux__panel-row"
                          data-selected={selected}
                          onClick={() => toggleModel(model.id)}
                          aria-pressed={selected}
                        >
                          <span>{model.name}</span>
                          <span>{selected ? model.provider : t("workspace.composer.notSelected")}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {error && <div className="new-ux__error" role="alert">{error}</div>}
            </section>
          ) : (
            <section className="new-ux__run">
              <div className="new-ux__desktop-run">
                <div>
                  <p className="new-ux__kicker">{t(mode.nameKey)} · {currentStatusLabel}</p>
                  <h1 className="new-ux__question">{workspace.debate?.prompt || question}</h1>

                  <div className="new-ux__section">
                    <p className="new-ux__section-title">{t("workspace.composer.panelLabel")}</p>
                    {liveRows.map((row) => (
                      <article key={row.name} className="new-ux__model">
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
                    <span>{workspace.synthesisState.status === "final" ? t("workspace.run.verdict") : t("workspace.run.verdictForming")}</span>
                    <span>{workspace.isPollingFallback ? t("workspace.run.polling") : workspace.sseStatus}</span>
                  </div>
                  <div className="new-ux__verdict-grid">
                    <div>
                      <div className="new-ux__verdict-word">
                        {modeId === "compare"
                          ? t("mode.compare.name")
                          : report?.verdict?.decision_type || (workspace.synthesisState.status === "failed" ? t("status.failed") : "—")}
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

                  {report && (
                    <div className="new-ux__report">
                      <p className="new-ux__kicker">{t("workspace.report.title")}</p>
                      <h2>{report.title || t("workspace.report.title")}</h2>
                      <div className="new-ux__report-rule" />
                      {typeof report.verdict?.confidence === "number" && (
                        <p className="new-ux__report-confidence">{Math.round(report.verdict.confidence * 100)}%</p>
                      )}
                      {report.executive_summary && <p>{report.executive_summary}</p>}
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
    </div>
  );
}
