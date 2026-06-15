"use client"

import { useState, useEffect, useCallback } from "react"
import { cn } from "@/lib/utils"
import { ChevronUp, List } from "lucide-react"

interface Section {
  id: string
  label: string
}

interface ReportSectionNavProps {
  sections: Section[]
  className?: string
}

export function ReportSectionNav({ sections, className }: ReportSectionNavProps) {
  const [activeId, setActiveId] = useState<string>(sections[0]?.id || "")
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    const observers: IntersectionObserver[] = []

    sections.forEach((section) => {
      const el = document.getElementById(section.id)
      if (!el) return

      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveId(section.id)
          }
        },
        { rootMargin: "-20% 0px -60% 0px", threshold: 0 }
      )

      observer.observe(el)
      observers.push(observer)
    })

    return () => observers.forEach((o) => o.disconnect())
  }, [sections])

  const scrollTo = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" })
      setIsExpanded(false)
    }
  }, [])

  return (
    <nav
      className={cn(
        "sticky top-0 z-30 bg-background/80 backdrop-blur-md border-b border-border/50",
        className
      )}
      aria-label="Report sections"
    >
      {/* Desktop: horizontal tabs */}
      <div className="hidden sm:flex items-center gap-1 px-4 py-2 overflow-x-auto">
        {sections.map((section) => (
          <button
            key={section.id}
            onClick={() => scrollTo(section.id)}
            className={cn(
              "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap",
              activeId === section.id
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            )}
          >
            {section.label}
          </button>
        ))}
      </div>

      {/* Mobile: expandable dropdown */}
      <div className="sm:hidden">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-foreground"
        >
          <span className="flex items-center gap-2">
            <List className="h-4 w-4 text-muted-foreground" />
            {sections.find((s) => s.id === activeId)?.label || "Sections"}
          </span>
          <ChevronUp
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              isExpanded && "rotate-180"
            )}
          />
        </button>
        {isExpanded && (
          <div className="border-t border-border/50 px-4 py-2 space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => scrollTo(section.id)}
                className={cn(
                  "w-full text-left px-3 py-2 text-sm rounded-lg transition-colors",
                  activeId === section.id
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                {section.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </nav>
  )
}
