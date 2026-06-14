"use client"

import { cn } from "@/lib/utils"
import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"

interface ReportSectionProps {
  title: string
  children: ReactNode
  className?: string
  empty?: boolean
  id?: string
  isActive?: boolean
  onVisible?: (id: string) => void
}

export function ReportSection({ title, children, className, empty, id, isActive, onVisible }: ReportSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!id || !onVisible || !sectionRef.current) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          onVisible(id)
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 }
    )

    observer.observe(sectionRef.current)
    return () => observer.disconnect()
  }, [id, onVisible])

  if (empty) return null
  return (
    <div
      ref={sectionRef}
      id={id}
      className={cn(
        "space-y-3 scroll-mt-20 transition-opacity duration-200",
        isActive && "opacity-100",
        className
      )}
    >
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      {children}
    </div>
  )
}
