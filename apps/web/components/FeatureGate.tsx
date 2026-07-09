"use client"

import React, { useEffect, useState } from "react"
import { isFeatureEnabled, FeatureFlag, subscribeToFeatureFlags } from "../lib/feature-flags"

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

export function useFeatureFlag(flag: FeatureFlag): boolean {
  const [enabled, setEnabled] = useState(() => isFeatureEnabled(flag))

  useEffect(() => {
    const unsubscribe = subscribeToFeatureFlags(() => {
      setEnabled(isFeatureEnabled(flag))
    })
    setEnabled(isFeatureEnabled(flag))
    return unsubscribe
  }, [flag])

  return enabled
}

export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const enabled = useFeatureFlag(flag)
  const usedFallback = !enabled && fallback !== null

  useEffect(() => {
    trackFeatureGate(flag, enabled, usedFallback)
  }, [flag, enabled, usedFallback])

  return <>{enabled ? children : fallback}</>
}
