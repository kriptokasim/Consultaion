export const featureFlags = {
  stagedDecisionPipeline: process.env.STAGED_DECISION_PIPELINE === "1",
  stagedDecisionPipelinePublic: process.env.NEXT_PUBLIC_STAGED_DECISION_PIPELINE === "1",
  unifiedWorkspace: process.env.NEXT_PUBLIC_UNIFIED_WORKSPACE === "1",
  mobileWorkspaceV2: process.env.NEXT_PUBLIC_MOBILE_WORKSPACE_V2 === "1",
  jitAuth: process.env.NEXT_PUBLIC_JIT_AUTH === "1",
  mobileReportV2: process.env.NEXT_PUBLIC_MOBILE_REPORT_V2 === "1",
} as const;

export type FeatureFlag = keyof typeof featureFlags;

export function isFeatureEnabled(flag: FeatureFlag): boolean {
  return featureFlags[flag];
}
