import { getDebateStats, getHealthStats, getRateLimitStats } from "@/lib/api";
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo";

export const dynamic = "force-dynamic";

export default async function OpsDashboardPage() {
  const [health, rateLimit, debates] = await Promise.all([
    getHealthStats().catch(() => null),
    getRateLimitStats().catch(() => null),
    getDebateStats().catch(() => null),
  ]);

  if (!health) {
    return (
      <main className="p-6">
        <p className="text-sm text-stone-600">Ops data unavailable. Ensure you are logged in as admin.</p>
      </main>
    );
  }

  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={32} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Admin Ops</p>
            <h1 className="text-3xl font-semibold text-stone-900">Operational overview</h1>
            <p className="text-sm text-stone-700">Rate limits, health signals, and recent debate activity.</p>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <HealthCard title="Database" ok={health.db_ok} />
        <HealthCard
          title="Redis backend"
          ok={health.redis_ok !== false}
          meta={health.rate_limit_backend}
        />
        <HealthCard title="Rate limiter" ok={true} meta={health.rate_limit_backend} />
        <HealthCard title="CSRF" ok={health.enable_csrf} meta={health.enable_csrf ? "Enabled" : "Disabled"} />
        <HealthCard title="Security headers" ok={health.enable_sec_headers} meta={health.enable_sec_headers ? "Enabled" : "Disabled"} />
        <HealthCard title="Mock mode" ok={!health.mock_mode} meta={health.mock_mode ? "Mock" : "Real LLM"} />
      </section>

      {debates ? (
        <section className="grid gap-4 md:grid-cols-4">
          <StatCard label="Total debates" value={debates.total} />
          <StatCard label="Last 24h" value={debates.last_24h} />
          <StatCard label="Last 7d" value={debates.last_7d} />
          <StatCard label="FAST_DEBATE" value={debates.fast_debate} />
        </section>
      ) : null}

      {rateLimit ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-stone-900">Recent rate-limit events</h2>
            <span className="text-xs text-stone-600">
              Window {rateLimit.window}s • Max calls {rateLimit.max_calls} • Backend {rateLimit.backend}
            </span>
          </div>
          <div className="overflow-hidden rounded-2xl border border-amber-100 bg-white shadow-sm">
            <div className="grid grid-cols-3 gap-3 border-b border-amber-100 bg-amber-100/60 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-amber-800">
              <span>IP</span>
              <span>Path</span>
              <span>Timestamp</span>
            </div>
            <div className="divide-y divide-amber-100">
              {rateLimit.recent_429s && rateLimit.recent_429s.length ? (
                rateLimit.recent_429s.map((event: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-3 gap-3 px-4 py-2 text-sm">
                    <span className="font-mono text-stone-800">{event.ip}</span>
                    <span className="text-stone-800">{event.path}</span>
                    <span className="text-stone-600">{event.ts}</span>
                  </div>
                ))
              ) : (
                <p className="px-4 py-3 text-sm text-stone-600">No recent 429 events.</p>
              )}
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function HealthCard({ title, ok, meta }: { title: string; ok: boolean; meta?: string }) {
  return (
    <div className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{title}</p>
      <div className="mt-2 flex items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
            ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-700"
          }`}
        >
          {ok ? "OK" : "Issue"}
        </span>
        {meta ? <span className="text-xs text-stone-700">{meta}</span> : null}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{label}</p>
      <p className="mt-1 text-xl font-semibold text-stone-900">{value}</p>
    </div>
  );
}
