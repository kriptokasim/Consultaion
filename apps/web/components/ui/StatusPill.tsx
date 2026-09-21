"use client";

import { useI18n } from "@/lib/i18n/client";
import { UI_RUN_STATUS_LABEL_KEYS, type UiRunStatus } from "@/lib/runStatusUi";

export interface StatusPillProps {
  status: UiRunStatus;
  className?: string;
}

/**
 * Canonical New UX status pill. Renders the four-value status vocabulary
 * (Live/Closed/Needs you/Failed) from lib/runStatusUi.ts — never a raw
 * backend status string.
 */
export function StatusPill({ status, className = "" }: StatusPillProps) {
  const { t } = useI18n();
  return (
    <span className={`new-ux-status-pill new-ux-status-pill--${status} ${className}`.trim()}>
      <span className="new-ux-status-pill__dot" aria-hidden="true" />
      {t(UI_RUN_STATUS_LABEL_KEYS[status])}
    </span>
  );
}
