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
    <div className="overflow-x-auto">
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
  )
}
