"use client"

import { Moon, Sun } from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"
import { BrandWordmark } from "@/components/brand"

interface AuthShellProps {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
}

export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  const [theme, setTheme] = useState<"light" | "dark">("light")

  useEffect(() => {
    if (typeof window === "undefined") return
    const stored = window.localStorage.getItem("consultaion-theme")
    const initial = stored === "dark" ? "dark" : "light"
    setTheme(initial)
    document.documentElement.classList.toggle("dark", initial === "dark")
  }, [])

  const toggleTheme = () => {
    if (typeof window === "undefined") return
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark"
      document.documentElement.classList.toggle("dark", next === "dark")
      window.localStorage.setItem("consultaion-theme", next)
      return next
    })
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] px-4 py-8">
      <div className="w-full max-w-md">
        <div className="relative">
          <div
            className="pointer-events-none absolute -inset-1 rounded-3xl bg-gradient-to-br from-amber-300/60 via-amber-500/40 to-amber-700/40 opacity-70 blur-xl"
            aria-hidden="true"
          />

          <div className="relative card-elevated auth-card px-6 py-8 dark:border-amber-200/40 sm:px-8 sm:py-10">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="focus-ring absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-full border border-amber-200/60 bg-white/90 text-amber-700 shadow-sm transition hover:-translate-y-[1px] dark:border-amber-200/30 dark:bg-white/10 dark:text-amber-50"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <header className="mb-6 space-y-2 text-center">
              <div className="flex justify-center">
                <BrandWordmark size="sm" className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-800 dark:text-amber-100" />
              </div>
              <h1 className="heading-serif text-2xl font-semibold text-amber-950 dark:text-amber-50 sm:text-3xl">{title}</h1>
              {subtitle ? <p className="text-sm auth-muted">{subtitle}</p> : null}
            </header>

            <div className="space-y-4">{children}</div>

            {footer ? (
              <footer className="mt-6 border-t border-amber-100/60 pt-4 text-center text-xs text-amber-900/70 dark:border-amber-200/20 dark:text-amber-100/70">
                {footer}
              </footer>
            ) : null}
          </div>
        </div>
      </div>
    </main>
  )
}
