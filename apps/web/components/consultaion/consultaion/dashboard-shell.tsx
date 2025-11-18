"use client"

import type React from "react"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { FileText, PlayCircle, Settings, Search, Moon, Sun, Shield, Scale, BarChart3, Trophy, BookOpen, Award, Menu, X, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useState, useEffect } from "react"
import { logout } from "@/lib/auth"
import { ToastProvider } from "@/components/ui/toast"
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo"

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: BarChart3 },
  { name: "Live", href: "/live", icon: PlayCircle },
  { name: "Runs", href: "/runs", icon: FileText },
  { name: "Chamber", href: "/chamber", icon: Scale },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Leaderboard", href: "/leaderboard", icon: Trophy },
  { name: "Hall of Fame", href: "/hall-of-fame", icon: Award },
  { name: "Models", href: "/models", icon: Award },
  { name: "Methodology", href: "/methodology", icon: BookOpen },
  { name: "Settings", href: "/settings", icon: Settings },
]

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const [profile, setProfile] = useState<{ email: string; role: string } | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("consultaion-theme") : null
    if (stored === "light" || stored === "dark") {
      setTheme(stored)
    }
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (theme === "dark") {
      root.classList.add("dark")
    } else {
      root.classList.remove("dark")
    }
    if (typeof window !== "undefined") {
      localStorage.setItem("consultaion-theme", theme)
    }
  }, [theme])

  useEffect(() => {
    let cancelled = false
    const loadProfile = async () => {
      try {
        const res = await fetch(`${apiBase}/me`, { credentials: "include", cache: "no-store" })
        if (!cancelled) {
          if (res.ok) {
            const data = await res.json()
            setProfile(data)
          } else {
            setProfile(null)
          }
        }
      } catch {
        if (!cancelled) {
          setProfile(null)
        }
      } finally {
        if (!cancelled) {
          setLoadingProfile(false)
        }
      }
    }
    loadProfile()
    return () => {
      cancelled = true
    }
  }, [apiBase])

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  const handleLogout = async () => {
    await logout()
    setProfile(null)
    window.location.href = "/login"
  }

  const navItems = [...navigation]
  if (profile?.role === "admin") {
    navItems.push({ name: "Admin", href: "/admin", icon: Shield })
    navItems.push({ name: "Ops", href: "/admin/ops", icon: Shield })
  }

  return (
    <ToastProvider>
      <div className="flex min-h-screen overflow-hidden bg-background text-foreground">
        {/* Sidebar */}
        <aside
          className={cn(
            "sidebar-surface fixed inset-y-0 left-0 z-40 w-72 flex-col border-r border-border px-4 py-6 shadow-2xl transition-transform duration-200 md:relative md:flex md:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          )}
          aria-label="Primary navigation"
        >
          <Link href="/home" className="flex items-center gap-3 border-b border-sidebar-border pb-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar">
            <RosettaChamberLogo size={32} className="drop-shadow" />
            <div className="leading-tight">
              <p className="text-[0.65rem] font-semibold uppercase tracking-[0.05em] text-amber-700">Consultaion</p>
              <p className="heading-serif text-lg font-semibold text-amber-900">Parliament</p>
            </div>
          </Link>
          <nav className="mt-4 flex-1 space-y-1" role="navigation">
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  title={
                    {
                      Live: "Run a new live debate and watch the chamber in real time.",
                      Runs: "Browse the full history of past debates and results.",
                      Chamber: "Visualize how votes and champions move through Consultaion.",
                      Analytics: "Aggregate stats across debates, models, and judges.",
                      Leaderboard: "Top-performing prompts and debates.",
                      "Hall of Fame": "Debates where one model’s answer became a Consultaion champion.",
                      Models: "Performance statistics for each AI model.",
                      Methodology: "How the chamber debates, scores, and selects champions.",
                      Settings: "Account and chamber configuration (coming soon).",
                      Admin: "Admin controls",
                      Ops: "Operational health and rate limits.",
                    }[item.name] || undefined
                  }
                  className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
                    isActive
                      ? "bg-gradient-to-r from-amber-100/90 to-amber-50 text-amber-900 shadow-inner shadow-amber-200/60 border border-amber-200/70"
                      : "text-sidebar-foreground hover:bg-amber-50/60 hover:text-amber-900 hover:-translate-y-[1px] hover:shadow-sm",
                  )}
                >
                  <span className={cn("rounded-lg border border-transparent p-1 transition-colors", isActive && "border-amber-200 bg-white/80 text-amber-700")}>
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="mt-4 space-y-3 border-t border-sidebar-border pt-4">
            <div className="rounded-xl border border-amber-100/80 bg-amber-50/90 px-3 py-2 text-xs font-semibold uppercase tracking-[0.08em] text-amber-900 shadow-sm dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Amber-Mocha cockpit, WCAG friendly
              </div>
            </div>
            {profile ? (
              <div className="flex items-center gap-3 rounded-xl bg-sidebar-accent/80 px-3 py-3 shadow-inner shadow-amber-900/5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sidebar-primary text-sidebar-primary-foreground">
                  {profile.email.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 text-sm">
                  <div className="font-semibold text-sidebar-foreground">{profile.email}</div>
                  <div className="text-xs text-muted-foreground capitalize">{profile.role}</div>
                </div>
              </div>
            ) : (
              <Button variant="outline" asChild className="w-full justify-center border-amber-200/90 text-amber-900 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-50 dark:hover:bg-amber-900/30">
                <Link href="/login">Sign In</Link>
              </Button>
            )}
          </div>
          <button
            type="button"
            className="absolute right-3 top-3 inline-flex items-center justify-center rounded-full p-1 text-amber-800 transition hover:bg-amber-100 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </aside>

        {/* Main content */}
        <div className="flex flex-1 flex-col overflow-hidden app-surface">
          {/* Header */}
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-amber-100/70 bg-card/90 px-4 backdrop-blur supports-[backdrop-filter]:backdrop-blur-md shadow-sm shadow-amber-900/5 md:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="inline-flex items-center justify-center rounded-lg border border-amber-200/80 bg-white/70 p-2 text-amber-800 shadow-sm transition hover:-translate-y-[1px] hover:bg-amber-50 focus-visible:ring-2 focus-visible:ring-amber-500 md:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" />
              </button>
              <Link href="/home" className="hidden items-center gap-2 md:flex focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:ring-offset-card rounded-lg px-1">
                <RosettaChamberLogo size={32} className="drop-shadow-sm" />
                <span className="heading-serif text-lg font-semibold text-amber-900">
                  ConsultAI on
                </span>
              </Link>
              <div className="relative w-64 lg:w-80">
                <label className="sr-only" htmlFor="global-search">
                  Search runs, prompts, or results
                </label>
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500" aria-hidden="true" />
                <Input
                  id="global-search"
                  type="search"
                  placeholder="Search runs, prompts, results..."
                  className="search-elevated w-full rounded-xl border-stone-200 bg-white pl-10 text-sm text-stone-800 placeholder:text-stone-500 shadow-inner shadow-amber-900/5 focus-visible:ring-amber-500 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card dark:border-amber-900/50 dark:bg-stone-900 dark:text-amber-50 dark:placeholder:text-amber-200/70"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              {profile ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    asChild
                    className="hidden sm:inline-flex border-amber-300 bg-white text-amber-900 hover:bg-amber-50 focus-visible:ring-amber-500"
                  >
                    <Link href="/dashboard">Dashboard</Link>
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleLogout} disabled={loadingProfile} className="hidden sm:inline-flex">
                    Logout
                  </Button>
                  <div className="ml-1 flex h-9 w-9 items-center justify-center rounded-full border border-amber-200/70 bg-amber-50/80 text-xs font-bold uppercase text-amber-800 shadow-inner shadow-amber-900/5">
                    {profile.email.charAt(0).toUpperCase()}
                  </div>
                </>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  aria-label="Sign in"
                  className="hidden sm:inline-flex border-amber-300 bg-white text-amber-900 hover:bg-amber-50 focus-visible:ring-amber-500"
                >
                  <Link href="/login">Sign in</Link>
                </Button>
              )}
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 overflow-auto bg-background/60 px-4 pb-8 pt-4 md:px-8">{children}</main>
        </div>
      </div>
    </ToastProvider>
  )
}
