import Link from "next/link";
import { getHallOfFame, getMembers } from "@/lib/api";

export const dynamic = "force-dynamic";

import { Suspense } from "react";

const sortOptions = [
  { value: "top", label: "Top" },
  { value: "recent", label: "Most recent" },
  { value: "closest", label: "Closest debates" },
];

function toDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  return value;
}

export default async function HallOfFamePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[]>>;
}) {
  const resolved = (await Promise.resolve(searchParams ?? {})) as Record<string, string | string[]>;
  const sort = typeof resolved?.sort === "string" ? resolved.sort : "top";
  const model = typeof resolved?.model === "string" ? resolved.model : undefined;
  const start = typeof resolved?.start === "string" ? resolved.start : undefined;
  const end = typeof resolved?.end === "string" ? resolved.end : undefined;

  const [{ items }, membersPayload] = await Promise.all([
    getHallOfFame({ sort, model, start_date: start, end_date: end }).catch(() => ({ items: [] })),
    getMembers().catch(() => ({ members: [] })),
  ]);
  const members = Array.isArray((membersPayload as any)?.members) ? (membersPayload as any).members : [];
  const modelOptions = [{ id: "", name: "All models" }, ...members.map((m: any) => ({ id: m.name ?? m.id, name: m.name ?? m.id }))];

  return (
    <main id="main" className="space-y-8 p-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Hall of Fame</p>
        <h1 className="text-3xl font-semibold text-stone-900">Distinguished Debates of the House of AI</h1>
        <p className="max-w-3xl text-sm text-stone-700">
          A gallery of standout runs where AI judges crowned a clear champion. Browse prompts, winning personas, and
          jump into the full debate transcript.
        </p>
      </header>

      <form className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4 shadow-sm" method="get">
        <div className="grid gap-4 md:grid-cols-3">
          <label className="flex flex-col text-sm text-stone-700">
            <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">Model</span>
            <select name="model" defaultValue={model ?? ""} className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900">
              {modelOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm text-stone-700">
            <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">Start date</span>
            <input
              type="date"
              name="start"
              defaultValue={toDate(start)}
              className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900"
            />
          </label>
          <label className="flex flex-col text-sm text-stone-700">
            <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">End date</span>
            <input
              type="date"
              name="end"
              defaultValue={toDate(end)}
              className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-wide text-amber-800">Sort</span>
            <select name="sort" defaultValue={sort} className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900">
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            className="inline-flex items-center rounded-lg border border-amber-300 bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-amber-700"
          >
            Apply
          </button>
        </div>
      </form>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 p-6 text-sm text-stone-600">
          No debates available yet. Run a new session to populate the Hall of Fame.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {items.map((card: any) => (
            <article
              key={card.id}
              className="flex h-full flex-col rounded-3xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-5 shadow-sm"
            >
              <div className="mb-3 space-y-2">
                <p className="text-[0.65rem] font-semibold uppercase tracking-wide text-amber-700">Prompt</p>
                <p className="line-clamp-3 text-sm leading-relaxed text-stone-900">{card.prompt}</p>
              </div>
              <div className="mb-3 rounded-2xl border border-amber-100 bg-amber-50/80 p-3">
                <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-amber-800">
                  <span>Champion</span>
                  {typeof card.champion_score === "number" ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-amber-800">
                      {card.champion_score.toFixed(2)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm font-semibold text-stone-900">
                  {card.champion ?? "Unknown model"}
                  {typeof card.runner_up_score === "number" && typeof card.champion_score === "number" ? (
                    <span className="ml-2 text-xs font-normal text-amber-700">
                      Won by {(card.champion_score - card.runner_up_score).toFixed(2)}
                    </span>
                  ) : null}
                </p>
                {card.champion_excerpt ? (
                  <p className="mt-2 line-clamp-3 text-sm text-stone-800">{card.champion_excerpt}</p>
                ) : (
                  <p className="mt-2 text-sm text-stone-600">Champion answer unavailable.</p>
                )}
              </div>
              <div className="flex-1" />
              <Link
                href={`/runs/${card.id}`}
                className="inline-flex items-center justify-center rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm font-semibold text-amber-800 transition hover:border-amber-400 hover:text-amber-900"
              >
                View debate →
              </Link>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
