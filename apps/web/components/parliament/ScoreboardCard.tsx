import type { ScoreItem } from "./types";

interface ScoreboardCardProps {
  scores: ScoreItem[];
  method?: string;
}

export default function ScoreboardCard({ scores, method }: ScoreboardCardProps) {
  const sorted = scores.slice().sort((a, b) => b.score - a.score);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-stone-500">
        <span>Aggregate scores</span>
        {method ? <span className="font-semibold text-amber-700">{method}</span> : null}
      </div>
      {sorted.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-4 text-sm text-stone-500">
          No scores have been recorded yet.
        </p>
      ) : (
        <div className="space-y-2">
          {sorted.map((item, index) => (
            <div key={item.persona} className="rounded-2xl border border-stone-100 bg-stone-50/60 p-3">
              <div className="flex items-center justify-between text-sm font-medium text-stone-800">
                <span>
                  {index + 1}. {item.persona}
                </span>
                <span className="font-mono text-stone-600">{item.score.toFixed(2)}</span>
              </div>
              {item.rationale ? (
                <p className="mt-1 text-xs text-stone-500 line-clamp-2">{item.rationale}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
