"use client";

import { useMemo } from "react";
import { useI18n } from "@/lib/i18n/client";

export type ConnectionStatus = "connected" | "reconnecting" | "degraded" | "offline" | "closed";

interface ConnectionIndicatorProps {
  status: ConnectionStatus;
  className?: string;
}

const STATUS_CONFIG: Record<
  ConnectionStatus,
  { color: string; pulse: boolean; labelKey: string }
> = {
  connected: {
    color: "bg-emerald-500",
    pulse: false,
    labelKey: "connection.connected",
  },
  reconnecting: {
    color: "bg-amber-500",
    pulse: true,
    labelKey: "connection.reconnecting",
  },
  degraded: {
    color: "bg-orange-500",
    pulse: false,
    labelKey: "connection.degraded",
  },
  offline: {
    color: "bg-red-500",
    pulse: false,
    labelKey: "connection.offline",
  },
  closed: {
    color: "bg-gray-400",
    pulse: false,
    labelKey: "connection.closed",
  },
};

export function ConnectionIndicator({ status, className }: ConnectionIndicatorProps) {
  const { t } = useI18n();
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.offline;

  return (
    <div
      className={`inline-flex items-center gap-1.5 text-xs ${className ?? ""}`}
      role="status"
      aria-label={t(config.labelKey)}
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${config.color} ${
          config.pulse ? "animate-pulse" : ""
        }`}
      />
      <span className="text-muted-foreground">{t(config.labelKey)}</span>
    </div>
  );
}

export default ConnectionIndicator;
