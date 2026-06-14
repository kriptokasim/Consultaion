"use client"

import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface ReportSectionProps {
  title: string
  children: ReactNode
  className?: string
  empty?: boolean
  id?: string
}

export function ReportSection({ title, children, className, empty, id }: ReportSectionProps) {
  if (empty) return null
  return (
    <div id={id} className={cn("space-y-3 scroll-mt-20", className)}>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      {children}
    </div>
  )
}
