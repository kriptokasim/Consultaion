import { Activity, ArrowUpRight, BarChart3, Clock, Hash, TrendingUp } from "lucide-react";

export interface AnalyticsActivityItem {
  id: string;
  title: string;
  timestamp: string;
  status: string;
}

export interface AnalyticsWinRate {
  persona: string;
  wins: number;
  total: number;
}

export interface AnalyticsData {
  totals: {
    debates: number;
    completed: number;
    completionRate: number;
    avgDurationMinutes: number;
  };
  winRates: AnalyticsWinRate[];
  scoreDistribution: { label: string; count: number }[];
  activity: AnalyticsActivityItem[];
}

interface AnalyticsDashboardProps {
  data: AnalyticsData;
}

export default function AnalyticsDashboard({ data }: AnalyticsDashboardProps) {
  return (
    <section className="space-y-6">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow-[0_20px_45px_rgba(120,113,108,0.12)]">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">
          Analytics overview
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-semibold text-stone-900">Chamber Analytics</h1>
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
            <BarChart3 className="h-4 w-4" />
            Sepia dashboard
          </span>
        </div>
        <p className="mt-3 text-sm text-stone-600">
          Totals update on each debate creation, completion and score export. Filter logic is intentionally
          lightweight for rapid iteration—heavy analytics belong in the data warehouse.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label="Debates total"
          value={data.totals.debates}
          icon={<Hash className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label="Completion rate"
          value={`${Math.round(data.totals.completionRate * 100)}%`}
          icon={<TrendingUp className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label="Avg duration"
          value={`${data.totals.avgDurationMinutes.toFixed(1)}m`}
          icon={<Clock className="h-4 w-4 text-amber-500" />}
        />
        <StatCard
          label="Completed runs"
          value={data.totals.completed}
          icon={<ArrowUpRight className="h-4 w-4 text-amber-500" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                Model win rates
              </p>
              <h3 className="text-xl font-semibold text-stone-900">Persona performance</h3>
            </div>
          </div>
          <div className="mt-6 space-y-4">
            {data.winRates.length === 0 ? (
              <EmptyState message="No completed debates yet." />
            ) : (
              data.winRates.map((rate) => (
                <div key={rate.persona} className="space-y-2 rounded-xl border border-stone-100 p-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-stone-800">{rate.persona}</span>
                    <span className="text-stone-500">
                      {rate.wins}/{rate.total} wins
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-stone-200">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all"
                      style={{
                        width: `${Math.min(100, (rate.wins / Math.max(1, rate.total)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                Score distribution
              </p>
              <h3 className="text-xl font-semibold text-stone-900">Judge ribbons</h3>
            </div>
          </div>
          <div className="mt-6 space-y-3">
            {data.scoreDistribution.length === 0 ? (
              <EmptyState message="No scores recorded." />
            ) : (
              data.scoreDistribution.map((bucket) => (
                <div key={bucket.label} className="flex items-center gap-3">
                  <span className="w-16 text-xs font-semibold uppercase tracking-wide text-stone-400">
                    {bucket.label}
                  </span>
                  <div className="flex-1 rounded-full bg-stone-100">
                    <div
                      className="h-2 rounded-full bg-amber-400/80"
                      style={{ width: `${Math.min(100, bucket.count * 10)}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-sm font-medium text-stone-600">
                    {bucket.count}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
          <Activity className="h-4 w-4 text-amber-500" />
          Recent activity
        </div>
        <div className="mt-4 divide-y divide-stone-100">
          {data.activity.length === 0 ? (
            <EmptyState message="No recent events logged." />
          ) : (
            data.activity.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm text-stone-700"
              >
                <div>
                  <p className="font-semibold text-stone-900">{item.title}</p>
                  <p className="text-xs text-stone-500">{item.status}</p>
                </div>
                <time className="text-xs font-semibold text-amber-700">
                  {new Date(item.timestamp).toLocaleString()}
                </time>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-inner">
      <div className="flex items-center justify-between text-stone-500">
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
        {icon}
      </div>
      <p className="mt-4 text-2xl font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-6 text-center text-sm text-stone-500">
      {message}
    </div>
  );
}
