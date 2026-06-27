"use client"

import type React from "react"

import { Link } from 'next-view-transitions'
import BackButton from "@/components/navigation/BackButton"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { FileText, PlayCircle, Settings, Search, Moon, Sun, Shield, Scale, BarChart3, Trophy, BookOpen, Award, Menu, X, ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useState, useEffect, useRef, Suspense } from "react"
import { useQuery } from "@tanstack/react-query"
import { getDebatesList } from "@/lib/apiClient"
import { useDebounce } from "@/hooks/use-debounce"
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
  { labelKey: "nav.participation", href: "/participation", icon: Award, tooltipKey: "nav.tooltip.participation" },
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

function SearchStatusPill({ status }: { status: string }) {
  const statusColors: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-300",
    scoring: "bg-purple-100 text-purple-800 dark:bg-purple-950/40 dark:text-purple-300",
    verifying: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300",
    failed: "bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300",
    queued: "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  }
  const colorClass = statusColors[status] || "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide ${colorClass}`}>
      {status}
    </span>
  )
}

function GlobalSearchInput() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { t } = useI18n()
  const [query, setQuery] = useState("")
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const debouncedQuery = useDebounce(query, 300)

  const { data, isLoading } = useQuery({
    queryKey: ["global-search", debouncedQuery],
    queryFn: () => getDebatesList({ q: debouncedQuery, limit: 5 }),
    enabled: debouncedQuery.trim().length >= 2,
  })

  useEffect(() => {
    const q = searchParams?.get("q") || ""
    setQuery(q)
  }, [searchParams])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setIsOpen(false)
    const trimmed = query.trim()
    if (trimmed) {
      router.push(`/runs?q=${encodeURIComponent(trimmed)}`)
    } else {
      router.push("/runs")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsOpen(false)
    }
  }

  const items = data?.items || []
  const hasResults = items.length > 0
  const showDropdown = isOpen && (isLoading || debouncedQuery.trim().length >= 2)

  return (
    <div ref={containerRef} className="relative w-full">
      <form onSubmit={handleSubmit} className="relative w-full">
        <label className="sr-only" htmlFor="global-search">
          {t("dashboardShell.search.aria")}
        </label>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500" aria-hidden="true" />
        <Input
          id="global-search"
          type="search"
          placeholder={t("dashboardShell.search.placeholder")}
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          onKeyDown={handleKeyDown}
          className="search-elevated w-full rounded-xl border-slate-200 bg-white pl-10 text-sm text-slate-800 placeholder:text-slate-500 shadow-inner shadow-slate-900/5 focus-visible:ring-primary focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-400"
        />
      </form>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 max-h-[320px] w-full overflow-y-auto rounded-xl border border-slate-200/80 bg-white/95 p-1 shadow-lg backdrop-blur-md dark:border-slate-800 dark:bg-slate-950/95">
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-4 text-xs text-slate-500 dark:text-slate-400">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
              <span>Searching...</span>
            </div>
          )}

          {!isLoading && items.length === 0 && debouncedQuery.trim().length >= 2 && (
            <div className="py-4 text-center text-xs text-slate-500 dark:text-slate-400">
              No runs found for &ldquo;{debouncedQuery}&rdquo;
            </div>
          )}

          {!isLoading && hasResults && (
            <div className="space-y-0.5">
              {items.map((item) => (
                <Link
                  key={item.id}
                  href={`/runs/${item.id}`}
                  onClick={() => setIsOpen(false)}
                  className="flex flex-col gap-1 rounded-lg px-3 py-2 text-left transition hover:bg-slate-100/80 dark:hover:bg-slate-900/80"
                >
                  <span className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {item.prompt}
                  </span>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-slate-400 dark:text-slate-500">
                      ID: {item.id.slice(0, 8)}...
                    </span>
                    <SearchStatusPill status={item.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
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
  const [isCollapsed, setIsCollapsed] = useState(false)
  const sidebarRef = useRef<HTMLElement>(null)
  const sidebarTriggerRef = useRef<HTMLButtonElement>(null)
  const apiBase = API_ORIGIN
  const { t } = useI18n()

  useEffect(() => {
    setMounted(true)
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("consultaion-sidebar-collapsed")
      if (stored === "true") {
        setIsCollapsed(true)
      }
    }
  }, [])

  // Body scroll lock and focus trap for mobile sidebar
  useEffect(() => {
    if (!sidebarOpen) return

    const previousActiveElement = document.activeElement as HTMLElement
    document.body.style.overflow = "hidden"
    document.body.style.overscrollBehavior = "contain"

    // Focus first focusable element in sidebar
    const timer = setTimeout(() => {
      const focusable = sidebarRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex="0"]'
      )
      if (focusable && focusable.length > 0) {
        focusable[0].focus()
      }
    }, 50)

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSidebarOpen(false)
        sidebarTriggerRef.current?.focus()
        return
      }

      if (e.key === "Tab" && sidebarRef.current) {
        const focusableElements = sidebarRef.current.querySelectorAll<HTMLElement>(
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

    return () => {
      document.body.style.overflow = ""
      document.body.style.overscrollBehavior = ""
      window.removeEventListener("keydown", handleKeyDown)
      clearTimeout(timer)
      previousActiveElement?.focus()
    }
  }, [sidebarOpen])

  const handleToggleCollapse = () => {
    const nextState = !isCollapsed
    setIsCollapsed(nextState)
    if (typeof window !== "undefined") {
      localStorage.setItem("consultaion-sidebar-collapsed", String(nextState))
    }
  }

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
          <header className="sticky top-0 z-30 flex h-14 md:h-12 items-center justify-between border-b border-border bg-card/90 px-4 backdrop-blur shadow-sm md:px-6">
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
          ref={sidebarRef}
          role="dialog"
          aria-modal={sidebarOpen ? "true" : undefined}
          aria-label="Primary navigation"
          className={cn(
            "sidebar-surface fixed inset-y-0 left-0 z-40 flex-col border-r border-border py-6 shadow-2xl transition-all duration-200 md:relative md:flex md:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
            isCollapsed ? "w-72 md:w-20 px-3" : "w-72 md:w-72 px-4"
          )}
        >
          <Link
            href="/live"
            className={cn(
              "flex items-center border-b border-sidebar-border pb-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
              isCollapsed ? "justify-center" : "gap-3"
            )}
          >
            <Brand height={32} className="drop-shadow" />
            {!isCollapsed && (
              <div className="leading-tight">
                <div className="text-[0.65rem] font-semibold uppercase tracking-[0.05em] text-amber-700 dark:text-amber-400">
                  <BrandWordmark size="sm" className="text-[0.65rem]" />
                </div>
                <p className="heading-serif text-lg font-semibold text-slate-800 dark:text-white">Arena</p>
              </div>
            )}
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
                    "group flex items-center rounded-xl py-2 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
                    isCollapsed ? "justify-center px-1" : "gap-3 px-3",
                    isActive
                      ? "bg-gradient-to-r from-amber-100/90 to-slate-50 text-slate-900 shadow-inner shadow-amber-200/60 border border-amber-200/70 dark:from-amber-900/50 dark:to-slate-800 dark:text-white dark:border-amber-700/50"
                      : "text-sidebar-foreground hover:bg-amber-50/60 hover:text-slate-900 hover:-translate-y-[1px] hover:shadow-sm dark:hover:bg-amber-900/30 dark:hover:text-white",
                  )}
                >
                  <span className={cn("rounded-lg border border-transparent p-1 transition-colors", isActive && "border-amber-200 bg-white/80 text-amber-700 dark:border-amber-600 dark:bg-slate-800")}>
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  {!isCollapsed && <span className="truncate">{item.name}</span>}
                  {!isCollapsed && item.href === "/participation" && (
                    <span className="ml-auto rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-600 dark:bg-amber-500/20 dark:text-amber-400">
                      Beta
                    </span>
                  )}
                </Link>
              )
            })}
          </nav>
          <div className="mt-4 space-y-3 border-t border-sidebar-border pt-4">
            {profile ? (
              <div className={cn(
                "flex items-center rounded-xl bg-sidebar-accent/80 shadow-inner shadow-amber-900/5",
                isCollapsed ? "justify-center p-2" : "gap-3 p-3"
              )}>
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sidebar-primary text-sidebar-primary-foreground">
                  {(profile.display_name || profile.email).charAt(0).toUpperCase()}
                </div>
                {!isCollapsed && (
                  <div className="flex-1 text-sm min-w-0">
                    <div className="font-semibold text-sidebar-foreground truncate">{profile.display_name || profile.email}</div>
                    <div className="text-xs text-muted-foreground capitalize">{profile.role}</div>
                  </div>
                )}
              </div>
            ) : (
              <Button variant="outline" asChild className={cn("w-full justify-center border-slate-200 text-slate-800 hover:bg-slate-50 dark:border-slate-600 dark:text-white dark:hover:bg-slate-700", isCollapsed && "px-1")}>
                <Link href="/login">{isCollapsed ? "Sign In" : t("nav.signIn")}</Link>
              </Button>
            )}
            {!isCollapsed && <LanguageSwitcher />}
          </div>
          <button
            type="button"
            className="absolute right-3 top-3 inline-flex items-center justify-center rounded-full h-11 w-11 text-slate-700 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700 md:hidden"
            onClick={() => {
              setSidebarOpen(false)
              sidebarTriggerRef.current?.focus()
            }}
            aria-label={t("dashboardShell.nav.close")}
          >
            <X className="h-5 w-5" />
          </button>

          {/* Collapse Toggle Button (desktop only) */}
          <button
            type="button"
            onClick={handleToggleCollapse}
            className="absolute -right-3 top-1/2 z-50 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-md transition-all hover:bg-slate-50 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white md:flex"
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-3.5 w-3.5" />
            ) : (
              <ChevronLeft className="h-3.5 w-3.5" />
            )}
          </button>
        </aside>

        {/* Main content */}
        <div className="flex flex-1 flex-col overflow-hidden app-surface">
          {/* Header */}
          <header className="sticky top-0 z-30 flex h-16 md:h-14 items-center justify-between border-b border-slate-200 bg-card/90 px-4 backdrop-blur supports-[backdrop-filter]:backdrop-blur-md shadow-sm shadow-slate-900/5 dark:border-slate-700 md:px-6">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
              <button
                ref={sidebarTriggerRef}
                type="button"
                className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white/70 h-11 w-11 text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-primary dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 md:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label={t("dashboardShell.nav.open")}
              >
                <Menu className="h-4 w-4" />
              </button>
              {pathname !== "/live" ? (
                <BackButton
                  onClick={handleBackClick}
                  label={t("nav.goBack")}
                />
              ) : null}
              <Link href="/live" className="flex items-center gap-2 md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-card rounded-lg px-1">
                <Brand height={32} className="drop-shadow-sm" />
                <span className="heading-serif text-lg font-semibold text-slate-800 dark:text-white">
                  <BrandWordmark size="md" inline />
                </span>
              </Link>
              <div className="relative hidden min-w-[180px] flex-1 sm:block lg:max-w-xl">
                <Suspense fallback={
                  <div className="relative w-full">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500" aria-hidden="true" />
                    <Input
                      id="global-search-fallback"
                      type="search"
                      placeholder={t("dashboardShell.search.placeholder")}
                      disabled
                      className="search-elevated w-full rounded-xl border-slate-200 bg-white pl-10 text-sm text-slate-800 placeholder:text-slate-500 shadow-inner shadow-slate-900/5 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-400 opacity-50"
                    />
                  </div>
                }>
                  <GlobalSearchInput />
                </Suspense>
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
