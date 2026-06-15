"use client"

import React from "react"
import { isFeatureEnabled, FeatureFlag } from "../lib/feature-flags"

interface FeatureGateProps {
  flag: FeatureFlag
  children: React.ReactNode
  fallback?: React.ReactNode
}

/**
 * Gates a component behind a feature flag.
 * Renders children when flag is enabled, fallback when disabled.
 */
export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const enabled = isFeatureEnabled(flag)
  return <>{enabled ? children : fallback}</>
}

/**
 * Hook version for conditional logic in components.
 */
export function useFeatureFlag(flag: FeatureFlag): boolean {
  return isFeatureEnabled(flag)
}
