"use client";

import { useI18n } from "@/lib/i18n/client";

export interface OfflineBarProps {
  visible: boolean;
  className?: string;
}

/**
 * Canonical New UX offline state. Must explicitly say the run continues
 * server-side (SCREEN-SPEC "State family") — never imply data is lost.
 */
export function OfflineBar({ visible, className = "" }: OfflineBarProps) {
  const { t } = useI18n();
  if (!visible) return null;
  return (
    <div className={`new-ux-offline-bar ${className}`.trim()} role="status" aria-live="polite">
      {t("offlineBar.message")}
    </div>
  );
}
