import Link from "next/link";
import { getModelDetail } from "@/lib/api";
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo";
import RosettaGlyphMini from "@/components/branding/RosettaGlyphMini";

export const dynamic = "force-dynamic";

export default async function ModelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await getModelDetail(id).catch(() => null);

  if (!data) {
    return (
      <main className="p-6">
        <p className="text-sm text-stone-600">Model stats unavailable.</p>
      </main>
    );
  }

  return (
    <main id="main" className="space-y-6 p-6">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <RosettaChamberLogo size={32} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Model analytics</p>
            <h1 className="text-3xl font-semibold text-stone-900">{data.model}</h1>
            <p className="text-sm text-stone-700">
              Win rate, participation, and recent debates involving this model/persona.
            </p>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Win rate"
          value={`${(data.win_rate * 100).toFixed(1)}%`}
          icon={<RosettaGlyphMini className="h-4 w-4 text-amber-700" />}
        />
        <StatCard label="Total debates" value={data.total_debates} />
        <StatCard
          label="Avg score"
          value={typeof data.avg_score_overall === "number" ? data.avg_score_overall.toFixed(2) : "—"}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-stone-900">Recent debates</h2>
        <div className="divide-y divide-amber-100 rounded-2xl border border-amber-100 bg-white shadow-sm">
          {Array.isArray(data.recent_debates) && data.recent_debates.length ? (
            data.recent_debates.map((debate: any) => (
              <Link
                key={debate.debate_id}
                href={`/runs/${debate.debate_id}`}
                className="flex flex-col gap-1 px-4 py-3 text-sm transition hover:bg-amber-50"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-900">{debate.prompt}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      debate.was_champion ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-700"
                    }`}
                  >
                    {debate.was_champion ? "Champion" : "Participant"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-stone-600">
                  <span>Champion: {debate.champion ?? "Unknown"}</span>
                  {typeof debate.champion_score === "number" ? <span>Score {debate.champion_score.toFixed(2)}</span> : null}
                  {debate.created_at ? <span> • {new Date(debate.created_at).toLocaleString()}</span> : null}
                </div>
              </Link>
            ))
          ) : (
            <p className="px-4 py-3 text-sm text-stone-600">No recent debates found.</p>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-stone-900">Sample champion answers</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {Array.isArray(data.champion_samples) && data.champion_samples.length ? (
            data.champion_samples.map((sample: any) => (
              <article key={sample.debate_id} className="flex h-full flex-col rounded-2xl border border-amber-100 bg-amber-50/60 p-4 shadow-sm">
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  <RosettaGlyphMini className="h-4 w-4" />
                  Prompt
                </p>
                <p className="mb-2 text-sm font-semibold text-stone-900">{sample.prompt}</p>
                {sample.excerpt ? (
                  <p className="flex-1 text-sm text-stone-800">{sample.excerpt}</p>
                ) : (
                  <p className="flex-1 text-sm text-stone-600">No excerpt available.</p>
                )}
                <Link
                  href={`/runs/${sample.debate_id}`}
                  className="mt-3 inline-flex items-center rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-amber-800 transition hover:border-amber-400"
                >
                  View debate →
                </Link>
              </article>
            ))
          ) : (
            <p className="text-sm text-stone-600">No champion examples yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-4 shadow-sm">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
        {icon ? icon : null}
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-stone-900">{value}</p>
    </div>
  );
}
