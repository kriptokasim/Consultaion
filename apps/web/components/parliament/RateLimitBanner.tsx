"use client"

import React, { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n/client";

type Props = {
  detail: string;
  resetAt?: string;
  actions?: React.ReactNode;
};

export default function RateLimitBanner({ detail, resetAt, actions }: Props) {
  const [countdown, setCountdown] = useState<string | null>(null)
  const { t } = useI18n()

  useEffect(() => {
    if (!resetAt) return
    const target = new Date(resetAt).getTime()
    if (Number.isNaN(target)) return
    const update = () => {
      const diff = target - Date.now()
      if (diff <= 0) {
        setCountdown("00:00:00")
        return
      }
      const seconds = Math.floor(diff / 1000)
      const hrs = String(Math.floor(seconds / 3600)).padStart(2, "0")
      const mins = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")
      const secs = String(seconds % 60).padStart(2, "0")
      setCountdown(`${hrs}:${mins}:${secs}`)
    }
    update()
    const id = window.setInterval(update, 1000)
    return () => window.clearInterval(id)
  }, [resetAt])

  return (
    <div className="flex items-start justify-between gap-4 rounded-3xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-900 shadow-sm">
      <div>
        <p className="font-semibold">{t("rateLimit.banner.title")}</p>
        <p className="mt-1 text-rose-800">{detail}</p>
        {resetAt ? (
          <p className="mt-1 text-xs uppercase tracking-wide text-rose-700">
            {t("rateLimit.banner.resetsPrefix")} {new Date(resetAt).toLocaleTimeString()}
            {countdown ? <span className="ml-2 font-mono text-rose-800">{countdown}</span> : null}
          </p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
