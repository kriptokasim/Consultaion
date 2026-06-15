"use client"

import { useEffect, useCallback, useState } from "react"
import { cn } from "@/lib/utils"
import { Maximize2, Minimize2, Compass } from "lucide-react"

interface ReportFocusModeProps {
  title?: string
  onExport?: () => void
  children: React.ReactNode
  className?: string
}

interface Section {
  id: string
  label: string
}

export function ReportFocusMode({
  title,
  onExport,
  children,
  className,
}: ReportFocusModeProps) {
  const [isActive, setIsActive] = useState(false)
  const [tocOpen, setTocOpen] = useState(false)
  const [sections, setSections] = useState<Section[]>([])

  // Discover sections from DOM
  useEffect(() => {
    if (!isActive) return
    const discovered: Section[] = []
    const sectionIds = [
      "report-verdict",
      "report-findings",
      "report-positions",
      "report-risks",
      "report-actions",
      "report-caveats",
    ]
    sectionIds.forEach((id) => {
      const el = document.getElementById(id)
      if (el) {
        const heading = el.querySelector("h3")
        discovered.push({
          id,
          label: heading?.textContent?.trim() || id,
        })
      }
    })
    setSections(discovered)
  }, [isActive])

  // Lock body scroll when active
  useEffect(() => {
    if (isActive) {
      document.body.style.overflow = "hidden"
      document.body.style.overscrollBehavior = "contain"
    } else {
      document.body.style.overflow = ""
      document.body.style.overscrollBehavior = ""
    }
    return () => {
      document.body.style.overflow = ""
      document.body.style.overscrollBehavior = ""
    }
  }, [isActive])

  const scrollToSection = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" })
      setTocOpen(false)
    }
  }, [])

  if (!isActive) {
    return (
      <button
        onClick={() => setIsActive(true)}
        className={cn(
          "inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700",
          "bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium",
          "text-slate-700 dark:text-slate-300 shadow-sm",
          "hover:bg-slate-50 dark:hover:bg-slate-700 transition",
          className
        )}
      >
        <Maximize2 className="h-4 w-4" />
        <span className="hidden sm:inline">Focus Mode</span>
      </button>
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-background dark:bg-stone-950 flex flex-col animate-in fade-in duration-200">
      {/* Sticky header */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/90 px-4 py-3.5 backdrop-blur-md">
        <h1 className="text-sm sm:text-base font-bold text-foreground truncate">
          {title || "Decision Report"} (Focus Mode)
        </h1>
        <div className="flex items-center gap-2">
          {onExport && (
            <button
              onClick={onExport}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm hover:bg-muted/40 transition"
            >
              Export
            </button>
          )}
          <button
            onClick={() => setIsActive(false)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm hover:bg-muted/40 transition"
          >
            <Minimize2 className="h-3.5 w-3.5" />
            Exit Focus
          </button>
        </div>
      </header>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-8 max-w-4xl mx-auto w-full space-y-8 pb-24 scroll-smooth">
        {children}
      </div>

      {/* Floating ToC */}
      {sections.length > 0 && (
        <div className="fixed bottom-4 right-4 z-40">
          <div className="relative">
            {tocOpen && (
              <div className="absolute bottom-12 right-0 bg-card border border-border rounded-xl shadow-lg p-3 w-56 space-y-1 animate-in slide-in-from-bottom-2 fade-in duration-150">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-2 pb-1.5 border-b border-border/60">
                  Jump to Section
                </p>
                {sections.map((sec) => (
                  <button
                    key={sec.id}
                    onClick={() => scrollToSection(sec.id)}
                    className="w-full text-left px-2 py-1.5 text-xs font-medium text-foreground rounded-lg hover:bg-muted/50 transition truncate block"
                  >
                    {sec.label}
                  </button>
                ))}
              </div>
            )}
            <button
              onClick={() => setTocOpen(!tocOpen)}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/95 transition-all active:scale-95"
            >
              <Compass className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
