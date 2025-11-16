import Link from "next/link";
import { getDebates, getReport } from "@/lib/api";

export const dynamic = "force-dynamic";

type HallCard = {
  id: string;
  prompt: string;
  champion?: string;
  championText?: string;
  score?: number;
  totalModels?: number;
};

const CARD_LIMIT = 12;

export default async function HallOfFamePage() {
  let debates: any[] = [];
  try {
    const payload = await getDebates({ limit: CARD_LIMIT });
    debates = Array.isArray(payload?.items) ? payload.items : [];
  } catch {
    debates = [];
  }

  const cards: HallCard[] = await Promise.all(
    debates.map(async (debate) => {
      let report: any = null;
      try {
        report = await getReport(debate.id);
      } catch {
        report = null;
      }
      const scores = Array.isArray(report?.scores) ? report.scores : [];
      const sortedScores = scores
        .filter((entry: any) => entry?.persona)
        .sort((a: any, b: any) => (typeof b.score === "number" && typeof a.score === "number" ? b.score - a.score : 0));
      const championEntry = sortedScores[0];
      const championText = typeof report?.final === "string" && report.final ? report.final : debate?.final_content;
      return {
        id: debate.id,
        prompt: debate.prompt ?? "Untitled debate",
        champion: championEntry?.persona,
        championText,
        score: typeof championEntry?.score === "number" ? championEntry.score : undefined,
        totalModels: sortedScores.length || undefined,
      };
    }),
  );

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

      {cards.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 p-6 text-sm text-stone-600">
          No debates available yet. Run a new session to populate the Hall of Fame.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
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
                  {typeof card.score === "number" ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-amber-800">
                      {card.score.toFixed(2)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm font-semibold text-stone-900">
                  {card.champion ?? "Unknown model"}
                  {card.totalModels ? (
                    <span className="ml-2 text-xs font-normal text-amber-700">(1 of {card.totalModels})</span>
                  ) : null}
                </p>
                {card.championText ? (
                  <p className="mt-2 line-clamp-3 text-sm text-stone-800">{card.championText}</p>
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
