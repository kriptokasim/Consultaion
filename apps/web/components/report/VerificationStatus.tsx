"use client"

import { cn } from "@/lib/utils"
import { ShieldCheck, ShieldAlert, ShieldQuestion, AlertTriangle } from "lucide-react"

interface VerificationStatusProps {
  status?: string
  hasHallucinations?: boolean
  needsRevision?: boolean
  verificationError?: boolean
  verificationSource?: string
  className?: string
}

type StatusLevel = "verified" | "warning" | "error" | "unknown"

function deriveLevel(
  status?: string,
  hasHallucinations?: boolean,
  needsRevision?: boolean,
  verificationError?: boolean
): StatusLevel {
  if (verificationError || hasHallucinations) return "error"
  if (status === "failed") return "error"
  if (status === "unverified" || needsRevision) return "warning"
  if (status === "verified" || status === "passed") return "verified"
  return "unknown"
}

const statusConfig: Record<StatusLevel, { icon: typeof ShieldCheck; color: string; bg: string; label: string }> = {
  verified: {
    icon: ShieldCheck,
    color: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/30",
    label: "Verified & Faithful",
  },
  warning: {
    icon: ShieldQuestion,
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/30",
    label: "Needs Review",
  },
  error: {
    icon: ShieldAlert,
    color: "text-rose-600 dark:text-rose-400",
    bg: "bg-rose-50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/30",
    label: "Verification Failed",
  },
  unknown: {
    icon: AlertTriangle,
    color: "text-slate-500 dark:text-slate-400",
    bg: "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700",
    label: "Unverified",
  },
}

export function VerificationStatus({
  status,
  hasHallucinations,
  needsRevision,
  verificationError,
  verificationSource,
  className,
}: VerificationStatusProps) {
  const level = deriveLevel(status, hasHallucinations, needsRevision, verificationError)
  const config = statusConfig[level]
  const Icon = config.icon

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
        config.bg,
        className
      )}
      role="status"
      aria-label={`Verification status: ${config.label}`}
    >
      <Icon className={cn("h-4 w-4 shrink-0", config.color)} />
      <span className={cn("font-medium", config.color)}>{config.label}</span>
      {verificationSource && level === "verified" && (
        <span className="text-xs text-muted-foreground ml-1">
          via {verificationSource}
        </span>
      )}
    </div>
  )
}
