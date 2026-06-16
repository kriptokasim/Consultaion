"use client"

import React, { useEffect } from "react"
import { isFeatureEnabled, FeatureFlag } from "../lib/feature-flags"

interface FeatureGateProps {
  flag: FeatureFlag
  children: React.ReactNode
  fallback?: React.ReactNode
}

function trackFeatureGate(flag: string, enabled: boolean, usedFallback: boolean) {
  try {
    if (typeof window !== "undefined" && (window as any).posthog) {
      (window as any).posthog.capture("feature_gate_evaluated", {
        flag,
        enabled,
        used_fallback: usedFallback,
      })
    }
  } catch {
    // analytics best-effort
  }
}

export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const enabled = isFeatureEnabled(flag)
  const usedFallback = !enabled && fallback !== null

  useEffect(() => {
    trackFeatureGate(flag, enabled, usedFallback)
  }, [flag, enabled, usedFallback])

  return <>{enabled ? children : fallback}</>
}

export function useFeatureFlag(flag: FeatureFlag): boolean {
  return isFeatureEnabled(flag)
}
