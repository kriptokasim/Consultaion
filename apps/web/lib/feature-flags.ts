const ENV_FLAGS = {
  stagedDecisionPipeline: process.env.STAGED_DECISION_PIPELINE === "1",
  stagedDecisionPipelinePublic: process.env.NEXT_PUBLIC_STAGED_DECISION_PIPELINE === "1",
  unifiedWorkspace: process.env.NEXT_PUBLIC_UNIFIED_WORKSPACE === "1",
  mobileWorkspaceV2: process.env.NEXT_PUBLIC_MOBILE_WORKSPACE_V2 === "1",
  jitAuth: process.env.NEXT_PUBLIC_JIT_AUTH === "1",
  mobileReportV2: process.env.NEXT_PUBLIC_MOBILE_REPORT_V2 === "1",
  llmOperationLimits: process.env.ENABLE_LLM_OPERATION_LIMITS === "1",
  prometheusMetrics: process.env.ENABLE_PROMETHEUS_METRICS === "1",
  otelTracing: process.env.ENABLE_OTEL_TRACING === "1",
  gdprSelfService: process.env.ENABLE_GDPR_SELF_SERVICE === "1",
  statusPage: process.env.NEXT_PUBLIC_STATUS_PAGE === "1",
  changelog: process.env.NEXT_PUBLIC_CHANGELOG === "1",
  offlineRecovery: process.env.NEXT_PUBLIC_OFFLINE_RECOVERY === "1",
} as const;

export type FeatureFlag = keyof typeof ENV_FLAGS;

let _serverFlags: Record<string, boolean> | null = null;
let _fetchPromise: Promise<void> | null = null;

async function fetchServerFlags(): Promise<void> {
  try {
    const res = await fetch("/api/config/features", { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      _serverFlags = {
        jitAuth: data.jitAuth ?? data.jit_auth ?? false,
        mobileReportV2: data.mobileReportV2 ?? data.mobile_report_v2 ?? false,
        stagedDecisionPipeline: data.staged_decision_pipeline ?? false,
      };
    }
  } catch {
    _serverFlags = {};
  }
}

function ensureServerFlags(): void {
  if (_serverFlags === null && !_fetchPromise) {
    _fetchPromise = fetchServerFlags();
  }
}

export function isFeatureEnabled(flag: FeatureFlag): boolean {
  ensureServerFlags();
  const envVal = ENV_FLAGS[flag];
  const serverVal = _serverFlags?.[flag];
  if (serverVal !== undefined) return serverVal;
  return envVal;
}

export function getFeatureFlags(): Record<FeatureFlag, boolean> {
  ensureServerFlags();
  const result = {} as Record<FeatureFlag, boolean>;
  for (const key of Object.keys(ENV_FLAGS) as FeatureFlag[]) {
    result[key] = isFeatureEnabled(key);
  }
  return result;
}

export const featureFlags = new Proxy({} as Record<FeatureFlag, boolean>, {
  get(_target, prop: string) {
    return isFeatureEnabled(prop as FeatureFlag);
  },
});
