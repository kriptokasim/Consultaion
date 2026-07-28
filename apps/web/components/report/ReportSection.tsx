"use client"

import { cn } from "@/lib/utils"
import { useEffect, useRef, useState } from "react"
import { ChevronDown } from "lucide-react"
import type { ReactNode } from "react"

interface ReportSectionProps {
  title: string
  children: ReactNode
  className?: string
  empty?: boolean
  id?: string
  isActive?: boolean
  onVisible?: (id: string) => void
  defaultOpen?: boolean
  collapsible?: boolean
}

export function ReportSection({ title, children, className, empty, id, isActive, onVisible, defaultOpen = true, collapsible = false }: ReportSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(defaultOpen)

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

  const toggle = () => setOpen((o) => !o)

  return (
    <div
      ref={sectionRef}
      id={id}
      className={cn(
        "scroll-mt-20 transition-opacity duration-200",
        isActive && "opacity-100",
        className
      )}
    >
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between gap-2 py-2 text-left sm:cursor-default sm:pointer-events-none"
        aria-expanded={open}
      >
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {title}
        </h3>
        {collapsible && (
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform sm:hidden",
              open && "rotate-180"
            )}
            aria-hidden
          />
        )}
      </button>
      <div
        className={cn(
          "space-y-3",
          collapsible && !open && "hidden sm:block"
        )}
      >
        {children}
      </div>
    </div>
  )
}
