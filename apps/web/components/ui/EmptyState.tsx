"use client";

import { useI18n } from "@/lib/i18n/client";

export interface EmptyStateProps {
  /** i18n key for the one-sentence serif explanation. */
  titleKey: string;
  /** i18n key for the single action's label; omit for no action. */
  actionLabelKey?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * Canonical New UX empty state: one serif explanation and one action
 * (SCREEN-SPEC "State family"). Not for loading or error — see
 * ListSkeleton and ErrorBanner for those.
 */
export function EmptyState({ titleKey, actionLabelKey, onAction, className = "" }: EmptyStateProps) {
  const { t } = useI18n();
  return (
    <div className={`new-ux-empty-state ${className}`.trim()} role="status">
      <p className="new-ux-empty-state__text">{t(titleKey)}</p>
      {actionLabelKey && onAction && (
        <button type="button" className="new-ux__secondary" onClick={onAction}>
          {t(actionLabelKey)}
        </button>
      )}
    </div>
  );
}
