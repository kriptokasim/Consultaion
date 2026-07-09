"use client"

import React, { createContext, useContext, useEffect, useState } from "react"
import { FeatureFlag, getFeatureFlags, isFeatureEnabled, subscribeToFeatureFlags } from "../lib/feature-flags"

const FeatureFlagContext = createContext<Record<FeatureFlag, boolean> | null>(null)

export function FeatureFlagProvider({ children }: { children: React.ReactNode }) {
  const [flags, setFlags] = useState<Record<FeatureFlag, boolean>>(getFeatureFlags())

  useEffect(() => {
    const unsubscribe = subscribeToFeatureFlags(() => {
      setFlags(getFeatureFlags())
    })
    setFlags(getFeatureFlags())
    return unsubscribe
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
