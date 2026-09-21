"use client";

import { useI18n } from "@/lib/i18n/client";

export interface ErrorBannerProps {
  /** What is true — a factual, reassuring statement (e.g. "Your run is safe."). */
  whatIsTrue: string;
  /** What was tried / what happened, in plain language. */
  whatWasTried?: string;
  /** Support/reference code shown for diagnosis. */
  referenceCode?: string;
  onRetry?: () => void;
  retryLabelKey?: string;
  className?: string;
}

/**
 * Canonical New UX error state: what is true, what was tried, a reference
 * code and retry (SCREEN-SPEC "State family"). Replaces the previously
 * unused placeholder at this path — repository-wide search confirmed it
 * had no consumers before this rewrite.
 */
export function ErrorBanner({
  whatIsTrue,
  whatWasTried,
  referenceCode,
  onRetry,
  retryLabelKey = "errorBanner.retry",
  className = "",
}: ErrorBannerProps) {
  const { t } = useI18n();
  return (
    <div className={`new-ux__error ${className}`.trim()} role="alert">
      <p className="new-ux-error-banner__true">{whatIsTrue}</p>
      {whatWasTried && <p className="new-ux-error-banner__tried">{whatWasTried}</p>}
      {referenceCode && (
        <p className="new-ux-error-banner__ref">{t("errorBanner.reference", { code: referenceCode })}</p>
      )}
      {onRetry && (
        <button type="button" className="new-ux__secondary" onClick={onRetry}>
          {t(retryLabelKey)}
        </button>
      )}
    </div>
  );
}
