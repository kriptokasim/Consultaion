"use client"

import type React from "react"

import { Link } from 'next-view-transitions'
import { usePathname, useRouter } from "next/navigation"
import { FileText, PlayCircle, Settings, Search, Moon, Sun, Shield, Scale, BarChart3, Trophy, BookOpen, Award, Menu, X, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useState, useEffect, useRef } from "react"
import { logout } from "@/lib/auth"
import { ToastProvider } from "@/components/ui/toast"
import Brand from "@/components/parliament/Brand"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import { useI18n } from "@/lib/i18n/client"
import { BrandWordmark } from "@/components/brand"
import { API_ORIGIN } from "@/lib/config/runtime"
import { useTheme } from "next-themes"

// NOTE: Marketing-only routes (pricing, leaderboard, hall-of-fame, models, methodology)
// live under (marketing) and are not linked from the authenticated sidebar to avoid
// tearing down the DashboardShell. They remain reachable via the public header/footer.
const BASE_NAV_LINKS = [
  { labelKey: "nav.arena", href: "/live", icon: PlayCircle, tooltipKey: "nav.tooltip.arena" },
  { labelKey: "nav.overview", href: "/dashboard", icon: BarChart3, tooltipKey: "nav.tooltip.overview" },
  { labelKey: "nav.runs", href: "/runs", icon: FileText, tooltipKey: "nav.tooltip.runs" },
  { labelKey: "nav.analytics", href: "/analytics", icon: BarChart3, tooltipKey: "nav.tooltip.analytics" },
  { labelKey: "nav.settings", href: "/settings", icon: Settings, tooltipKey: "nav.tooltip.settings" },
]

type CurrentUserProfile = {
  email: string
  role: string
  display_name?: string | null
  avatar_url?: string | null
  is_admin?: boolean
}

type DashboardShellProps = {
  children: React.ReactNode
  initialProfile?: CurrentUserProfile | null
}

export default function DashboardShell({ children, initialProfile }: DashboardShellProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const hasInitialProfile = typeof initialProfile !== "undefined"
  const [profile, setProfile] = useState<CurrentUserProfile | null>(hasInitialProfile ? initialProfile ?? null : null)
  const [loadingProfile, setLoadingProfile] = useState(!hasInitialProfile)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const apiBase = API_ORIGIN
  const { t } = useI18n()

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (hasInitialProfile) {
      setProfile(initialProfile ?? null)
      setLoadingProfile(false)
      return
    }
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
  }, [apiBase, hasInitialProfile, initialProfile])

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark")
  }

  const handleBackClick = () => {
    // Prefer history back when available, otherwise return to the Arena.
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back()
      return
    }
    router.push("/live")
  }

  const handleLogout = async () => {
    try {
      await logout()
    } catch (e) {
      console.error("Logout API call failed", e)
    }
    setProfile(null)
    if (typeof window !== "undefined") {
      localStorage.clear()
      window.location.href = "/"
    }
  }

  const navItems = BASE_NAV_LINKS.map((item) => ({
    ...item,
    name: t(item.labelKey),
    tooltip: item.tooltipKey ? t(item.tooltipKey) : undefined,
  }))
  const isAdmin = Boolean(profile?.is_admin || profile?.role === "admin")
  if (isAdmin) {
    navItems.push({ labelKey: "nav.admin", tooltipKey: "nav.tooltip.admin", name: t("nav.admin"), href: "/admin", icon: Shield, tooltip: t("nav.tooltip.admin") })
    navItems.push({ labelKey: "nav.ops", tooltipKey: "nav.tooltip.ops", name: t("nav.ops"), href: "/admin/ops", icon: Shield, tooltip: t("nav.tooltip.ops") })
  }

  const isPublicRunView = !profile && !loadingProfile && pathname.startsWith("/runs/");

  if (isPublicRunView) {
    return (
      <ToastProvider>
        <div className="flex min-h-screen flex-col bg-background text-foreground">
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-card/90 px-4 backdrop-blur shadow-sm md:px-6">
            <div className="flex items-center gap-3">
              <Brand height={32} />
              <div className="leading-tight">
                <span className="heading-serif text-lg font-semibold"><BrandWordmark size="md" inline /></span>
              </div>
              <span className="ml-4 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary hidden sm:inline-block">
                Shared Arena Run
              </span>
            </div>
            <div className="flex items-center gap-3">
              <Button asChild variant="default" size="sm">
                <Link href={`/login?source=public_run&intent=create_own_run&next=${encodeURIComponent('/live?focus=prompt')}`}>
                  Create your own Arena run
                </Link>
              </Button>
            </div>
          </header>
          <main className="flex-1 overflow-auto app-surface">
            {children}
          </main>
        </div>
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <div className="flex min-h-screen overflow-hidden bg-background text-foreground">
        {/* Mobile Sidebar Overlay */}
        {sidebarOpen && (
          <div 
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden" 
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        
        {/* Sidebar */}
        <aside
          className={cn(
            "sidebar-surface fixed inset-y-0 left-0 z-40 w-72 flex-col border-r border-border px-4 py-6 shadow-2xl transition-transform duration-200 md:relative md:flex md:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          )}
          aria-label="Primary navigation"
        >
          <Link href="/live" className="flex items-center gap-3 border-b border-sidebar-border pb-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar">
            <Brand height={32} className="drop-shadow" />
            <div className="leading-tight">
              <div className="text-[0.65rem] font-semibold uppercase tracking-[0.05em] text-amber-700 dark:text-amber-400">
                <BrandWordmark size="sm" className="text-[0.65rem]" />
              </div>
              <p className="heading-serif text-lg font-semibold text-slate-800 dark:text-white">Arena</p>
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
                  title={item.tooltip}
                  className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
                    isActive
                      ? "bg-gradient-to-r from-amber-100/90 to-slate-50 text-slate-900 shadow-inner shadow-amber-200/60 border border-amber-200/70 dark:from-amber-900/50 dark:to-slate-800 dark:text-white dark:border-amber-700/50"
                      : "text-sidebar-foreground hover:bg-amber-50/60 hover:text-slate-900 hover:-translate-y-[1px] hover:shadow-sm dark:hover:bg-amber-900/30 dark:hover:text-white",
                  )}
                >
                  <span className={cn("rounded-lg border border-transparent p-1 transition-colors", isActive && "border-amber-200 bg-white/80 text-amber-700 dark:border-amber-600 dark:bg-slate-800")}>
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="mt-4 space-y-3 border-t border-sidebar-border pt-4">
            {profile ? (
              <div className="flex items-center gap-3 rounded-xl bg-sidebar-accent/80 px-3 py-3 shadow-inner shadow-amber-900/5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sidebar-primary text-sidebar-primary-foreground">
                  {(profile.display_name || profile.email).charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 text-sm">
                  <div className="font-semibold text-sidebar-foreground">{profile.display_name || profile.email}</div>
                  <div className="text-xs text-muted-foreground capitalize">{profile.role}</div>
                </div>
              </div>
            ) : (
              <Button variant="outline" asChild className="w-full justify-center border-slate-200 text-slate-800 hover:bg-slate-50 dark:border-slate-600 dark:text-white dark:hover:bg-slate-700">
                <Link href="/login">{t("nav.signIn")}</Link>
              </Button>
            )}
            <LanguageSwitcher />
          </div>
          <button
            type="button"
            className="absolute right-3 top-3 inline-flex items-center justify-center rounded-full p-1 text-slate-700 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label={t("dashboardShell.nav.close")}
          >
            <X className="h-5 w-5" />
          </button>
        </aside>

        {/* Main content */}
        <div className="flex flex-1 flex-col overflow-hidden app-surface">
          {/* Header */}
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-card/90 px-4 backdrop-blur supports-[backdrop-filter]:backdrop-blur-md shadow-sm shadow-slate-900/5 dark:border-slate-700 md:px-6">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
              <button
                type="button"
                className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white/70 p-2 text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-primary dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 md:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label={t("dashboardShell.nav.open")}
              >
                <Menu className="h-4 w-4" />
              </button>
              {pathname !== "/live" ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="inline-flex items-center gap-2 border-slate-300 bg-white/95 text-slate-800 shadow-sm hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:hover:bg-slate-700"
                  onClick={handleBackClick}
                  aria-label={t("nav.goBack")}
                >
                  <ArrowLeft className="h-4 w-4" />
                  <span>{t("nav.goBack")}</span>
                </Button>
              ) : null}
              <Link href="/live" className="flex items-center gap-2 md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-card rounded-lg px-1">
                <Brand height={32} className="drop-shadow-sm" />
                <span className="heading-serif text-lg font-semibold text-slate-800 dark:text-white">
                  <BrandWordmark size="md" inline />
                </span>
              </Link>
              <div className="relative hidden min-w-[180px] flex-1 sm:block lg:max-w-xl">
                <label className="sr-only" htmlFor="global-search">
                  {t("dashboardShell.search.aria")}
                </label>
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500" aria-hidden="true" />
                <Input
                  id="global-search"
                  type="search"
                  placeholder={t("dashboardShell.search.placeholder")}
                  className="search-elevated w-full rounded-xl border-slate-200 bg-white pl-10 text-sm text-slate-800 placeholder:text-slate-500 shadow-inner shadow-slate-900/5 focus-visible:ring-primary focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-400"
                  suppressHydrationWarning
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              {mounted && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleTheme}
                  aria-label="Toggle theme"
                  className="rounded-full text-muted-foreground hover:text-foreground h-9 w-9"
                >
                  {resolvedTheme === "dark" ? (
                    <Sun className="h-4 w-4" />
                  ) : (
                    <Moon className="h-4 w-4" />
                  )}
                </Button>
              )}
              {profile ? (
                <UserDropdown
                  profile={profile}
                  onLogout={handleLogout}
                  loadingProfile={loadingProfile}
                />
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  aria-label={t("nav.signIn")}
                  className="hidden sm:inline-flex border-slate-300 bg-white text-slate-800 hover:bg-slate-50 focus-visible:ring-primary dark:border-slate-600 dark:text-white dark:hover:bg-slate-700"
                >
                  <Link href="/login">{t("nav.signIn")}</Link>
                </Button>
              )}
            </div>
          </header>

          {/* Page content */}
          <main id="main-content" className="flex-1 overflow-auto bg-background/60 px-4 pb-8 pt-4 md:px-8">{children}</main>
        </div>
      </div>
    </ToastProvider>
  )
}

function UserDropdown({
  profile,
  onLogout,
  loadingProfile,
}: {
  profile: CurrentUserProfile
  onLogout: () => void
  loadingProfile: boolean
}) {
  const [open, setOpen] = useState(false)
  const { t } = useI18n()
  const dropdownRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false)
        triggerRef.current?.focus()
        return
      }

      if (e.key === "Tab" && dropdownRef.current) {
        const focusableElements = dropdownRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex="0"]'
        )
        if (focusableElements.length === 0) return

        const first = focusableElements[0]
        const last = focusableElements[focusableElements.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === first) {
            last.focus()
            e.preventDefault()
          }
        } else {
          if (document.activeElement === last) {
            first.focus()
            e.preventDefault()
          }
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    
    // Focus first focusable element inside the dropdown when opened
    const timer = setTimeout(() => {
      const focusable = dropdownRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex="0"]'
      )
      if (focusable && focusable.length > 0) {
        focusable[0].focus()
      }
    }, 50)

    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      clearTimeout(timer)
    }
  }, [open])

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-amber-50 text-xs font-bold uppercase text-slate-700 shadow-inner shadow-slate-900/5 transition hover:bg-amber-100 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:hover:bg-slate-600"
        aria-haspopup="true"
        aria-expanded={open}
      >
        {(profile.display_name || profile.email).charAt(0).toUpperCase()}
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            ref={dropdownRef}
            className="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 py-1 shadow-lg"
          >
            <div className="border-b border-slate-100 dark:border-slate-700 px-4 py-2">
              <p className="text-sm font-semibold text-slate-800 dark:text-white truncate">
                {profile.display_name || profile.email}
              </p>
              <p className="text-xs text-slate-600 dark:text-slate-300 truncate">{profile.email}</p>
            </div>
            <Link
              href="/live"
              onClick={() => setOpen(false)}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-slate-800 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              <PlayCircle className="h-4 w-4" />
              {t("nav.arena")}
            </Link>
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-slate-800 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              <Settings className="h-4 w-4" />
              {t("nav.settings")}
            </Link>
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                onLogout()
              }}
              disabled={loadingProfile}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30"
            >
              <X className="h-4 w-4" />
              {t("auth.logout")}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
