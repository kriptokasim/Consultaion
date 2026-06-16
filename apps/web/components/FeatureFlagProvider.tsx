"use client"

import React, { createContext, useContext, useEffect, useState } from "react"
import { FeatureFlag, getFeatureFlags, isFeatureEnabled } from "../lib/feature-flags"

const FeatureFlagContext = createContext<Record<FeatureFlag, boolean> | null>(null)

export function FeatureFlagProvider({ children }: { children: React.ReactNode }) {
  const [flags, setFlags] = useState<Record<FeatureFlag, boolean>>(getFeatureFlags())

  useEffect(() => {
    async function loadFlags() {
      try {
        const res = await fetch("/api/config/features", { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setFlags(prev => ({
            ...prev,
            jitAuth: data.jitAuth ?? data.jit_auth ?? prev.jitAuth,
            mobileReportV2: data.mobileReportV2 ?? data.mobile_report_v2 ?? prev.mobileReportV2,
            stagedDecisionPipeline: data.staged_decision_pipeline ?? prev.stagedDecisionPipeline,
          }))
        }
      } catch (e) {
        // Ignore error and rely on getFeatureFlags default initialized state
      }
    }
    loadFlags()
  }, [])

  return <FeatureFlagContext.Provider value={flags}>{children}</FeatureFlagContext.Provider>
}

export function useReactiveFeatureFlag(flag: FeatureFlag): boolean {
  const context = useContext(FeatureFlagContext)
  if (!context) {
    return isFeatureEnabled(flag)
  }
  return context[flag]
}
