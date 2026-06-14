"use client"

interface ModelPosition {
  model: string
  stance: string
  distinct_contribution?: string
  blind_spot?: string
  strongest_point?: string
  concern?: string
}

interface ModelPositionsTableProps {
  positions: ModelPosition[]
}

const stanceColors: Record<string, string> = {
  supportive: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  concerned: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  neutral: "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  opposing: "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
}

export function ModelPositionsTable({ positions }: ModelPositionsTableProps) {
  if (!positions.length) return null

  return (
    <div>
      {/* Mobile view: Stacked cards */}
      <div className="grid grid-cols-1 gap-3 md:hidden">
        {positions.map((pos, i) => (
          <div
            key={i}
            className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-3 bg-card/65 shadow-xs"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-slate-900 dark:text-white">{pos.model}</span>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${stanceColors[pos.stance] || stanceColors.neutral}`}>
                {pos.stance}
              </span>
            </div>
            
            {(pos.distinct_contribution || pos.strongest_point) && (
              <div className="space-y-1">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">Distinct Contribution</span>
                <p className="text-xs text-slate-700 dark:text-slate-350 leading-relaxed">
                  {pos.distinct_contribution || pos.strongest_point}
                </p>
              </div>
            )}
            
            {(pos.blind_spot || pos.concern) && (
              <div className="space-y-1">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase block">Blind Spot / Limitation</span>
                <p className="text-xs text-slate-605 dark:text-slate-400 leading-relaxed">
                  {pos.blind_spot || pos.concern}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Desktop view: Traditional table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800">
              <th className="pb-2 text-left font-semibold text-slate-500 dark:text-slate-400">Model</th>
              <th className="pb-2 text-left font-semibold text-slate-500 dark:text-slate-400">Stance</th>
              <th className="pb-2 text-left font-semibold text-slate-500 dark:text-slate-400">Distinct Contribution</th>
              <th className="pb-2 text-left font-semibold text-slate-500 dark:text-slate-400">Blind Spot / Limitation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/50">
            {positions.map((pos, i) => (
              <tr key={i}>
                <td className="py-3 font-medium text-slate-900 dark:text-white whitespace-nowrap">{pos.model}</td>
                <td className="py-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${stanceColors[pos.stance] || stanceColors.neutral}`}>
                    {pos.stance}
                  </span>
                </td>
                <td className="py-3 text-slate-600 dark:text-slate-400 max-w-xs">{pos.distinct_contribution || pos.strongest_point || ""}</td>
                <td className="py-3 text-slate-600 dark:text-slate-400 max-w-xs">{pos.blind_spot || pos.concern || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
