import Link from "next/link";
import { getModelLeaderboard } from "@/lib/api";
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const models = await getModelLeaderboard().catch(() => []);
  if (!models || models.length === 0) {
    return (
      <main id="main" className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={36} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Model stats</p>
            <h1 className="text-3xl font-semibold text-stone-900">Performance across debates</h1>
          </div>
        </div>
        <div className="rounded-3xl border border-dashed border-stone-200 bg-white/80 p-6 text-center shadow-sm">
          <p className="text-base font-semibold text-stone-900">No model stats yet</p>
          <p className="mt-2 text-sm text-stone-600">
            Once you’ve run a few debates, each model’s win rate, average score, and total debates will be tracked here.
          </p>
          <div className="mt-4">
            <Link
              href="/"
              className="inline-flex items-center rounded-lg border border-amber-200 bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-amber-500"
            >
              Run a debate
            </Link>
          </div>
        </div>
      </main>
    );
  }
  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={36} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Model stats</p>
            <h1 className="text-3xl font-semibold text-stone-900">Performance across debates</h1>
          </div>
        </div>
        <p className="max-w-3xl text-sm text-stone-700">How each model fares in Consultaion debates.</p>
      </header>

      <div className="overflow-hidden rounded-2xl border border-amber-100 bg-amber-50/70 shadow-sm">
        <div className="grid grid-cols-4 gap-3 border-b border-amber-100 bg-amber-100/60 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-amber-800">
          <span>Model</span>
          <span>Win rate</span>
          <span>Total debates</span>
          <span>Avg score</span>
        </div>
        <div className="divide-y divide-amber-100 bg-white">
          {models.map((item: any) => (
            <Link
              key={item.model}
              href={`/models/${encodeURIComponent(item.model)}`}
              className="grid grid-cols-4 items-center gap-3 px-4 py-3 text-sm transition-all duration-200 hover:-translate-y-[1px] hover:bg-amber-50 hover:shadow-sm"
            >
              <span className="font-semibold text-stone-900">{item.model}</span>
              <span className="text-amber-800">{(item.win_rate * 100).toFixed(1)}%</span>
              <span className="text-stone-700">{item.total_debates}</span>
              <span className="font-mono text-stone-800">
                {typeof item.avg_champion_score === "number" ? item.avg_champion_score.toFixed(2) : "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
