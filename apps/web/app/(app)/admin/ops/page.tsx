import { fetchWithAuth } from "@/lib/auth"
import { getServerTranslations } from "@/lib/i18n/server"

export const dynamic = "force-dynamic"

type RateLimitSummary = {
  backend?: string
  redis_ok?: boolean | null
  recent_429_count?: number
}

type SseSummary = {
  backend?: string
  redis_ok?: boolean | null
}

type ProviderHealthRow = {
  provider?: string
  model?: string
  error_rate?: number
  total_calls?: number
  is_open?: boolean
  last_opened?: string | null
}

type OpsSummaryResponse = {
  debates_24h?: number
  debates_7d?: number
  active_users_24h?: number
  tokens_24h?: number
  postgres_ok?: boolean
  top_models?: Array<{ model_name: string; total_tokens: number }>
  rate_limit?: RateLimitSummary
  sse?: SseSummary
  models?: { available?: boolean; enabled_count?: number }
  parliament?: {
    seat_counts?: Record<string, number>
    model_usage_by_role?: Array<{ role: string; provider?: string; model?: string; total_tokens: number }>
  }
  provider_health?: ProviderHealthRow[]
}

export default async function AdminOpsPage() {
  const { t } = await getServerTranslations()
  const response = await fetchWithAuth("/admin/ops/summary")
  const payload = (await response.json().catch(() => ({}))) as OpsSummaryResponse

  const metricCards = [
    {
      label: "Debates (24h)",
      value: payload.debates_24h ?? 0,
      description: `${payload.debates_7d ?? 0} over seven days`,
    },
    {
      label: "Tokens (24h)",
      value: Intl.NumberFormat().format(payload.tokens_24h ?? 0),
      description: "Approximate usage across models",
    },
    {
      label: "Active users",
      value: payload.active_users_24h ?? 0,
      description: "Unique debaters in the last day",
    },
  ]

  const rateLimitHealthy =
    payload.rate_limit?.backend === "redis" ? payload.rate_limit?.redis_ok !== false : true
  const sseHealthy = payload.sse?.backend === "redis" ? payload.sse?.redis_ok !== false : true

  const statusItems = [
    { label: "Postgres", healthy: payload.postgres_ok !== false, description: "Primary database" },
    {
      label: `Rate limit (${payload.rate_limit?.backend ?? "memory"})`,
      healthy: rateLimitHealthy,
      description: `${payload.rate_limit?.recent_429_count ?? 0} recent 429s`,
    },
    {
      label: `SSE (${payload.sse?.backend ?? "memory"})`,
      healthy: sseHealthy,
      description: payload.sse?.backend === "redis" ? (payload.sse?.redis_ok ? "Redis reachable" : "Redis unreachable") : "Memory backend",
    },
    {
      label: "Models",
      healthy: payload.models?.available ?? false,
      description: `${payload.models?.enabled_count ?? 0} enabled`,
    },
  ]

  const topModels = payload.top_models ?? []
  const seatCounts = payload.parliament?.seat_counts ?? {}
  const modelUsage = payload.parliament?.model_usage_by_role ?? []
  const providerHealth = payload.provider_health ?? []

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Ops & health</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950 dark:text-amber-50">Runtime telemetry</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Keep tabs on debates, tokens, and infrastructure touchpoints.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        {metricCards.map((card) => (
          <MetricCard key={card.label} label={card.label} value={card.value} description={card.description} />
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Top models</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">Token-heavy models across all time.</p>
          <div className="mt-4 space-y-2">
            {topModels.length ? (
              topModels.map((model) => (
                <div
                  key={model.model_name}
                  className="flex items-center justify-between rounded-2xl bg-white/80 px-3 py-2 text-sm font-semibold text-stone-700 shadow-inner shadow-amber-100"
                >
                  <span>{model.model_name}</span>
                  <span>{Intl.NumberFormat().format(model.total_tokens)}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-stone-500">No usage yet.</p>
            )}
          </div>
        </div>
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Runtime signals</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">Current backend readiness and provider stats.</p>
          <div className="mt-4 space-y-3">
            {statusItems.map((item) => (
              <StatusRow key={item.label} label={item.label} healthy={item.healthy} description={item.description} />
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Seat usage</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">How often each role is scheduled in panels.</p>
          <div className="mt-4 space-y-2">
            {Object.keys(seatCounts).length ? (
              Object.entries(seatCounts).map(([role, count]) => (
                <div key={role} className="flex items-center justify-between rounded-2xl border border-amber-100 px-3 py-2 text-sm font-semibold text-stone-700 dark:border-amber-900/40 dark:text-amber-50">
                  <span className="capitalize">{role.replace(/_/g, " ")}</span>
                  <span>{count}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-stone-500">No parliament usage yet.</p>
            )}
          </div>
        </div>
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Model usage by role</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">Token totals grouped by role + provider.</p>
          <div className="mt-4 space-y-2">
            {modelUsage.length ? (
              modelUsage.map((entry) => (
                <div key={`${entry.role}-${entry.model}-${entry.provider}`} className="rounded-2xl border border-amber-100 px-3 py-2 text-sm text-stone-700 dark:border-amber-900/40 dark:text-amber-50">
                  <p className="font-semibold capitalize">{entry.role.replace(/_/g, " ")}</p>
                  <p className="text-xs text-stone-500">
                    {entry.provider ?? "provider"} · {entry.model ?? "model"}
                  </p>
                  <p className="font-mono text-sm text-stone-900 dark:text-amber-50">{Intl.NumberFormat().format(entry.total_tokens)}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-stone-500">No token data recorded yet.</p>
            )}
          </div>
        </div>
      </section>

      <section className="card-elevated p-5">
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">{t("admin.ops.providerHealth.title")}</h2>
        <p className="text-sm text-stone-500 dark:text-stone-400">{t("admin.ops.providerHealth.description")}</p>
        <div className="mt-4 space-y-2">
          {providerHealth.length ? (
            providerHealth.map((entry) => {
              const errorRate = Math.round((entry.error_rate ?? 0) * 100)
              const status = entry.is_open
                ? ("circuitOpen" as const)
                : errorRate >= 50
                  ? ("degraded" as const)
                  : ("healthy" as const)
              return (
                <div
                  key={`${entry.provider}-${entry.model}`}
                  className="flex items-center justify-between rounded-2xl border border-amber-100/50 bg-white/70 px-4 py-3 shadow-sm dark:border-amber-900/40 dark:bg-stone-900"
                >
                  <div>
                    <p className="text-sm font-semibold text-stone-900 dark:text-stone-100">
                      {entry.provider ?? t("admin.ops.providerHealth.provider")}
                    </p>
                    <p className="text-xs text-stone-500 dark:text-stone-400">
                      {entry.model ?? t("admin.ops.providerHealth.model")} ·{" "}
                      {(entry.total_calls ?? 0).toString()} {t("admin.ops.providerHealth.callsLabel")}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="font-mono text-sm text-stone-900 dark:text-amber-50">{errorRate}%</p>
                    <HealthBadge status={status} label={t(`admin.ops.providerHealth.status.${status}`)} />
                  </div>
                </div>
              )
            })
          ) : (
            <p className="text-sm text-stone-500 dark:text-stone-400">{t("admin.ops.providerHealth.empty")}</p>
          )}
        </div>
      </section>
    </div>
  )
}

function MetricCard({ label, value, description }: { label: string; value: number | string; description?: string }) {
  return (
    <div className="glass-card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-stone-900 dark:text-stone-100">{value}</p>
      {description ? <p className="text-sm text-stone-500 dark:text-stone-400">{description}</p> : null}
    </div>
  )
}

function StatusRow({ label, healthy, description }: { label: string; healthy?: boolean; description?: string }) {
  const state = healthy === false ? "down" : healthy ? "ok" : "unknown"
  const badgeClass =
    state === "ok"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : state === "down"
        ? "bg-red-50 text-red-700 border-red-200"
        : "bg-stone-50 text-stone-700 border-stone-200"

  const badgeText = state === "ok" ? "Healthy" : state === "down" ? "Attention" : "Unknown"

  return (
    <div className="flex items-center justify-between rounded-2xl border border-amber-100/50 bg-white/70 px-4 py-3 shadow-sm dark:bg-stone-900">
      <div>
        <p className="text-sm font-semibold text-stone-900 dark:text-stone-100">{label}</p>
        {description ? <p className="text-xs text-stone-500 dark:text-stone-400">{description}</p> : null}
      </div>
      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${badgeClass}`}>{badgeText}</span>
    </div>
  )
}

function HealthBadge({ status, label }: { status: "healthy" | "degraded" | "circuitOpen"; label: string }) {
  const className =
    status === "healthy"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : status === "degraded"
        ? "bg-amber-50 text-amber-800 border-amber-200"
        : "bg-red-50 text-red-700 border-red-200"

  return <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${className}`}>{label}</span>
}
