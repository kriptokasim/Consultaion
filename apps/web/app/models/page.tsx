import Link from "next/link";
import { getModelLeaderboard } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const models = await getModelLeaderboard().catch(() => []);
  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Model stats</p>
        <h1 className="text-3xl font-semibold text-stone-900">Performance across debates</h1>
        <p className="max-w-3xl text-sm text-stone-700">
          Win rates and participation metrics for each persona/model based on judge scores.
        </p>
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
              className="grid grid-cols-4 items-center gap-3 px-4 py-3 text-sm transition hover:bg-amber-50"
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
