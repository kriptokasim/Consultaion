"use client"

import type React from "react"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { FileText, PlayCircle, Settings, Search, Moon, Sun, User, Shield, Scale, BarChart3, Trophy, BookOpen, Award } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useState, useEffect } from "react"
import { logout } from "@/lib/auth"
import { ToastProvider } from "@/components/ui/toast"
import RosettaChamberLogo from "@/components/branding/RosettaChamberLogo"

const navigation = [
  { name: "Live", href: "/", icon: PlayCircle },
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
      <div className="flex h-screen overflow-hidden bg-background">
        {/* Sidebar */}
      <aside className="hidden w-64 flex-col border-r border-border bg-sidebar md:flex">
        <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-6">
          <RosettaChamberLogo size={32} className="drop-shadow" />
          <span className="font-semibold text-sidebar-foreground">Rosetta Chamber</span>
        </div>
        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.name}
                href={item.href}
                title={
                  {
                    Live: "Run a new live debate and watch the chamber in real time.",
                    Runs: "Browse the full history of past debates and results.",
                    Chamber: "Visualize how votes and champions move through the Rosetta chamber.",
                    Analytics: "Aggregate stats across debates, models, and judges.",
                    Leaderboard: "Top-performing prompts and debates.",
                    "Hall of Fame": "Debates where one model’s answer became a Rosetta champion.",
                    Models: "Performance statistics for each AI model.",
                    Methodology: "How the chamber debates, scores, and selects champions.",
                    Settings: "Account and chamber configuration (coming soon).",
                    Admin: "Admin controls",
                    Ops: "Operational health and rate limits.",
                  }[item.name] || undefined
                }
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            )
          })}
        </nav>
        <div className="border-t border-sidebar-border p-4">
          {profile ? (
            <div className="flex items-center gap-3 rounded-lg bg-sidebar-accent px-3 py-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-primary text-sidebar-primary-foreground">
                {profile.email.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 text-sm">
                <div className="font-medium text-sidebar-foreground">{profile.email}</div>
                <div className="text-xs text-muted-foreground capitalize">{profile.role}</div>
              </div>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center justify-center rounded-lg bg-sidebar-accent px-3 py-2 text-sm font-medium text-sidebar-accent-foreground"
            >
              Sign In
            </Link>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-16 items-center justify-between border-b border-border bg-card px-6">
          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-2 md:flex">
              <span className="text-sm font-semibold text-stone-700 dark:text-stone-200">
                Consultaion · Rosetta Chamber
              </span>
            </div>
            <div className="relative w-64 lg:w-80">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type="search" placeholder="Search runs, prompts, results..." className="pl-10 bg-background" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggleTheme} className="h-9 w-9">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            {profile ? (
              <Button variant="ghost" size="sm" onClick={handleLogout} disabled={loadingProfile}>
                Logout
              </Button>
            ) : (
              <Button variant="outline" size="sm" asChild aria-label="Sign in">
                <Link href="/login">Sign in</Link>
              </Button>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto bg-background">{children}</main>
      </div>
    </div>
    </ToastProvider>
  )
}
