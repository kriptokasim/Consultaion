"use client"

interface ConfidenceDonutProps {
  confidence: number
  size?: number
  label?: string
}

export function ConfidenceDonut({ confidence, size = 80, label }: ConfidenceDonutProps) {
  const pct = Math.round(confidence * 100)
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  const color =
    pct >= 75 ? "text-emerald-500" :
    pct >= 50 ? "text-amber-500" :
    "text-red-500"

  const strokeColor =
    pct >= 75 ? "#10b981" :
    pct >= 50 ? "#f59e0b" :
    "#ef4444"

  return (
    <div className="flex flex-col items-center gap-1" role="img" aria-label={`Confidence: ${pct}%`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          className="text-slate-200 dark:text-slate-700"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <span className={cn("text-lg font-bold", color)}>
        {pct}%
      </span>
      {label && (
        <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {label}
        </span>
      )}
    </div>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ")
}
