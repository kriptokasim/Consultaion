"use client"

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import Link from "next/link"
import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { Copy, Eye, Loader2, Share2, Pin, PinOff, LayoutGrid, List } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { ApiError, assignDebateTeam, TeamSummary, getDebates, normalizeRunStatus } from "@/lib/api"
import SearchFilter from "@/components/ui/search-filter"
import EmptyState from "@/components/ui/empty-state"
import { useDebounce } from "@/hooks/use-debounce"
import { useToast } from "@/components/ui/toast"
import StatusBadge from "@/components/parliament/StatusBadge"
import { useI18n } from "@/lib/i18n/client"

type Run = {
  id: string
  prompt: string
  status: string
  created_at: string
  updated_at: string
  user_id?: string | null
  team_id?: string | null
  mode?: string
  verdict?: {
    decision_type?: string
    confidence?: number
    rationale?: string
  } | null
}

type Scope = "mine" | "team" | "all"

const SCOPE_KEYS: Record<Scope, string> = {
  mine: "runs.scope.mine",
  team: "runs.scope.team",
  all: "runs.scope.all",
}

type RunsTableProps = {
  items: Run[]
  teams: TeamSummary[]
  profile?: { id: string; role: string } | null
  initialQuery?: string
  initialStatus?: string | null
}

function normalizeStatus(status?: string) {
  return normalizeRunStatus(status ?? null)
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: () => void) {
  useEffect(() => {
    function handle(event: MouseEvent) {
      if (!ref.current || ref.current.contains(event.target as Node)) return
      handler()
    }
    document.addEventListener("mousedown", handle)
    return () => document.removeEventListener("mousedown", handle)
  }, [handler, ref])
}

function getInitialScope(profile: { id: string; role: string } | null | undefined): Scope {
  if (!profile) return "all"
  return profile.role === "admin" ? "all" : "mine"
}

const VERDICT_STYLES: Record<string, { label: string; cls: string }> = {
  proceed:     { label: "PROCEED",     cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200" },
  reject:      { label: "REJECT",      cls: "bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200" },
  investigate: { label: "INVESTIGATE", cls: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200" },
  mixed:       { label: "MIXED",       cls: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300" },
}

function RunCard({ run, isPinned, onTogglePin }: { run: Run; isPinned: boolean; onTogglePin: (id: string) => void }) {
  const verdictType = run.verdict?.decision_type?.toLowerCase() || ""
  const vc = VERDICT_STYLES[verdictType]
  const confidence = run.verdict?.confidence
    ? Math.round(run.verdict.confidence * 100)
    : null

  return (
    <Link
      href={`/runs/${run.id}`}
      className={cn("group block rounded-2xl border bg-card hover:border-primary/40 hover:shadow-md transition-all p-5 space-y-3", isPinned ? "border-amber-200/50 bg-amber-50/20" : "border-border")}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <button 
            onClick={(e) => { e.preventDefault(); onTogglePin(run.id); }}
            className={cn("p-1 rounded-md transition-colors", isPinned ? "text-amber-500 bg-amber-100/50" : "text-muted-foreground hover:text-foreground")}
            aria-label="Pin run"
          >
            <Pin className={cn("h-3.5 w-3.5", isPinned ? "fill-current" : "")} />
          </button>
          {run.mode && (
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              {run.mode}
            </span>
          )}
          <StatusBadge status={normalizeStatus(run.status)} />
        </div>
        <span className="text-[11px] text-muted-foreground shrink-0">
          {new Date(run.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </span>
      </div>

      {/* Prompt */}
      <p className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
        {run.prompt}
      </p>

      {/* Verdict badge */}
      {vc && (
        <div className="flex items-center gap-2 mt-auto pt-2">
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-black tracking-widest uppercase ${vc.cls}`}>
            {vc.label}
          </span>
          {confidence !== null && (
            <span className="text-[11px] text-muted-foreground">{confidence}% confidence</span>
          )}
        </div>
      )}
    </Link>
  )
}

export default function RunsTable({ items, teams, profile, initialQuery = "", initialStatus = null }: RunsTableProps) {
  const { t } = useI18n()
  const profileId = profile?.id ?? null
  const isAdmin = profile?.role === "admin"
  const hasProfile = Boolean(profileId)
  const [scope, setScope] = useState<Scope>(() => getInitialScope(profile))
  const scopeWasManuallyChangedRef = useRef(false)

  const handleScopeChange = useCallback((option: Scope) => {
    scopeWasManuallyChangedRef.current = true
    setScope(option)
  }, [])

  useEffect(() => {
    if (scopeWasManuallyChangedRef.current) return
    setScope(getInitialScope(profile))
  }, [profile])
  const [rows, setRows] = useState(items)
  const [search, setSearch] = useState(initialQuery)
  const [statusFilter, setStatusFilter] = useState<string | null>(initialStatus)
  const [viewFilter, setViewFilter] = useState<"all" | "arena" | "this_week">("all")
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid")
  const [pinnedRuns, setPinnedRuns] = useState<string[]>([])
  const debouncedSearch = useDebounce(search, 300)
  const { pushToast } = useToast()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const searchParamsString = searchParams?.toString() || ""
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    try {
      const stored = localStorage.getItem("consultaion_pinned_runs")
      if (stored) setPinnedRuns(JSON.parse(stored))
    } catch (e) {}
  }, [])

  const togglePin = (id: string) => {
    setPinnedRuns(prev => {
      const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
      localStorage.setItem("consultaion_pinned_runs", JSON.stringify(next))
      return next
    })
  }

  useEffect(() => {
    setSearch(initialQuery)
  }, [initialQuery])

  useEffect(() => {
    setStatusFilter(initialStatus)
  }, [initialStatus])

  useEffect(() => {
    if (debouncedSearch || statusFilter) return
    setRows(items)
  }, [items, debouncedSearch, statusFilter])

  const teamMap = useMemo(() => Object.fromEntries(teams.map((team) => [team.id, team.name])), [teams])

  const availableScopes: Scope[] = !hasProfile 
    ? ["all"] 
    : isAdmin 
      ? ["mine", "team", "all"] 
      : ["mine", "team"]

  const filteredRuns = useMemo(() => {
    const lowerQuery = debouncedSearch.trim().toLowerCase()
    return rows.filter((run) => {
      if (scope === "mine" && profileId && run.user_id !== profileId && run.user_id) return false
      if (scope === "team" && !run.team_id) return false
      if (statusFilter && run.status !== statusFilter) return false
      if (lowerQuery) {
        const searchableText = [run.id, run.prompt, run.mode, run.status]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
        if (!searchableText.includes(lowerQuery)) return false
      }
      if (viewFilter === "arena" && run.mode !== "arena") return false
      if (viewFilter === "this_week") {
        const oneWeekAgo = new Date()
        oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
        if (new Date(run.created_at) < oneWeekAgo) return false
      }
      return true
    })
  }, [rows, scope, profileId, debouncedSearch, statusFilter, viewFilter])

  const paginatedRuns = useMemo(() => {
    return [...filteredRuns].sort((a, b) => {
      const aPinned = pinnedRuns.includes(a.id)
      const bPinned = pinnedRuns.includes(b.id)
      if (aPinned && !bPinned) return -1
      if (!aPinned && bPinned) return 1
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
  }, [filteredRuns, pinnedRuns])

  const handleAssignTeam = useCallback(
    async (runId: string, teamId: string | null) => {
      try {
        await assignDebateTeam(runId, teamId)
        setRows((prev) => prev.map((run) => (run.id === runId ? { ...run, team_id: teamId ?? null } : run)))
        pushToast({
          title: teamId ? t("runs.toast.shared") : t("runs.toast.private"),
          variant: "success",
        })
      } catch (error) {
        if (error instanceof ApiError) {
          const detail = typeof error.body === "object" && error.body?.detail ? error.body.detail : error.message
          pushToast({ title: t("runs.toast.shareError"), description: detail, variant: "error" })
          throw new Error(detail)
        }
        pushToast({ title: t("runs.toast.shareError"), variant: "error" })
        throw new Error(t("runs.toast.shareError"))
      }
    },
    [setRows, pushToast, t],
  )

  const copyToClipboard = (text: string) => {
    navigator.clipboard
      ?.writeText(text)
      .then(() => pushToast({ title: t("runs.toast.copySuccess"), variant: "success" }))
      .catch(() => pushToast({ title: t("runs.toast.copyError"), variant: "error" }))
  }

  const truncate = (str: string, length: number) => {
    return str.length > length ? `${str.slice(0, length)}…` : str
  }

  useEffect(() => {
    const params = new URLSearchParams(searchParamsString)
    if (debouncedSearch) {
      params.set("q", debouncedSearch)
    } else {
      params.delete("q")
    }
    if (statusFilter) {
      params.set("status", statusFilter)
    } else {
      params.delete("status")
    }
    const next = params.toString()
    router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false })
  }, [debouncedSearch, statusFilter, pathname, router, searchParamsString])

  useEffect(() => {
    if (!debouncedSearch && !statusFilter) {
      return
    }
    let active = true
    setSearchLoading(true)
    getDebates(
      {
        limit: 100,
        offset: 0,
        q: debouncedSearch || undefined,
        status: statusFilter || undefined,
      },
      { auth: true },
    )
      .then((response) => {
        if (!active) return
        setRows(response.items ?? [])
      })
      .catch((error) => {
        pushToast({
          title: t("runs.error.fetchTitle"),
          description: error instanceof Error ? error.message : t("runs.error.fetchDescription"),
          variant: "error",
        })
      })
      .finally(() => {
        if (active) setSearchLoading(false)
      })
    return () => {
      active = false
    }
  }, [debouncedSearch, statusFilter, pushToast, t])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-gradient-to-r from-white via-amber-50 to-white p-4">
        <div className="flex items-center gap-2 rounded-full bg-white/70 p-1 text-sm font-medium text-stone-600">
          {availableScopes.map((option) => (
            <button
              key={option}
              className={cn(
                "rounded-full px-3 py-1 transition",
                scope === option ? "bg-amber-600 text-white shadow" : "text-stone-600 hover:text-stone-900",
              )}
              onClick={() => handleScopeChange(option)}
            >
              {t(SCOPE_KEYS[option])}
            </button>
          ))}
        </div>
        <p className="text-xs text-stone-500">{t("runs.scope.note")}</p>
      </div>
      
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={viewFilter === "all" ? "default" : "outline"}
          size="sm"
          className={cn("rounded-full", viewFilter === "all" ? "bg-stone-800 text-white" : "")}
          onClick={() => setViewFilter("all")}
        >
          All Runs
        </Button>
        <Button
          variant={viewFilter === "arena" ? "default" : "outline"}
          size="sm"
          className={cn("rounded-full", viewFilter === "arena" ? "bg-amber-600 hover:bg-amber-700 text-white border-amber-600" : "")}
          onClick={() => setViewFilter("arena")}
        >
          Arena Only
        </Button>
        <Button
          variant={viewFilter === "this_week" ? "default" : "outline"}
          size="sm"
          className={cn("rounded-full", viewFilter === "this_week" ? "bg-stone-800 text-white" : "")}
          onClick={() => setViewFilter("this_week")}
        >
          This Week
        </Button>
      </div>

      <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
        <button
          onClick={() => setViewMode("grid")}
          className={`p-1.5 rounded-md text-sm transition-colors ${viewMode === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
          aria-label="Grid view"
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          onClick={() => setViewMode("table")}
          className={`p-1.5 rounded-md text-sm transition-colors ${viewMode === "table" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
          aria-label="Table view"
        >
          <List className="h-4 w-4" />
        </button>
      </div>
      </div>

      <SearchFilter
        value={search}
        onValueChange={setSearch}
        status={statusFilter}
        onStatusChange={setStatusFilter}
        statuses={[
          { value: "completed", label: t("runs.statusFilter.completed") },
          { value: "running", label: t("runs.statusFilter.running") },
          { value: "queued", label: t("runs.statusFilter.queued") },
          { value: "failed", label: t("runs.statusFilter.failed") },
        ]}
        placeholder={t("runs.filter.placeholder")}
        clearLabel={t("runs.filter.clear")}
      />
      {searchLoading ? <p className="text-xs text-stone-500">{t("runs.searching")}</p> : null}

      {viewMode === "grid" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {paginatedRuns.map((run) => (
            <RunCard 
              key={run.id} 
              run={run} 
              isPinned={pinnedRuns.includes(run.id)}
              onTogglePin={togglePin}
            />
          ))}
        </div>
      ) : (
      <div className="rounded-3xl border border-stone-200 bg-white shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-stone-100">
              <TableHead className="w-[120px] font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.run")}</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.prompt")}</TableHead>
              <TableHead className="w-[120px] font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.status")}</TableHead>
              <TableHead className="w-[140px] font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.team")}</TableHead>
              <TableHead className="w-[150px] font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.created")}</TableHead>
              <TableHead className="w-[150px] font-mono text-xs uppercase tracking-wide text-stone-400">{t("runs.table.columns.updated")}</TableHead>
              <TableHead className="w-[180px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedRuns.map((run) => {
              const isPinned = pinnedRuns.includes(run.id)
              return (
              <TableRow key={run.id} className={cn("border-b hover:bg-amber-50/40", isPinned ? "bg-amber-50/20 border-amber-200/50" : "border-stone-50")}>
                <TableCell className="font-mono text-xs text-stone-600">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn("h-6 w-6", isPinned ? "text-amber-500 hover:text-amber-600 hover:bg-amber-100/50" : "text-stone-300 hover:text-stone-500")}
                      onClick={() => togglePin(run.id)}
                      aria-label="Pin run"
                    >
                      {isPinned ? <Pin className="h-3.5 w-3.5 fill-current" /> : <Pin className="h-3.5 w-3.5" />}
                    </Button>
                    <span>{truncate(run.id, 8)}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-stone-500 hover:text-stone-900"
                      aria-label={t("runs.table.copyId")}
                      onClick={() => copyToClipboard(run.id)}
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell className="text-sm text-stone-900">{truncate(run.prompt, 80)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={normalizeStatus(run.status)} />
                    {run.mode && (
                      <span className="rounded-md border border-amber-200/50 bg-amber-100/50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/30 dark:text-amber-200">
                        {run.mode}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {run.team_id ? (
                    <Badge className="bg-amber-100 text-amber-900">
                      {teamMap[run.team_id] ?? t("runs.table.shared")}
                    </Badge>
                  ) : (
                    <span className="text-xs uppercase tracking-wide text-stone-400">{t("runs.table.private")}</span>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs text-stone-500">
                  {new Date(run.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="font-mono text-xs text-stone-500">
                  {new Date(run.updated_at).toLocaleString()}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {(normalizeStatus(run.status) === "completed" || normalizeStatus(run.status) === "failed") ? (
                      <Link href={`/runs/${run.id}/replay`} className="text-xs font-semibold text-amber-700 underline-offset-4 hover:underline">
                        {t("dashboard.recentDebates.replay")}
                      </Link>
                    ) : null}
                    <Link href={`/runs/${run.id}`} className="inline-flex">
                      <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={t("runs.table.view")}>
                        <Eye className="h-4 w-4" />
                      </Button>
                    </Link>
                    {hasProfile && teams.length > 0 ? (
                      <SharePopover
                        currentTeamId={run.team_id}
                        teams={teams}
                        onAssign={(teamId) => handleAssignTeam(run.id, teamId)}
                        labels={{
                          heading: t("runs.share.heading"),
                          keepPrivate: t("runs.share.keepPrivate"),
                          cancel: t("runs.share.cancel"),
                          apply: t("runs.share.apply"),
                          error: t("runs.share.error"),
                          button: t("runs.share.buttonLabel"),
                        }}
                      />
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            )})}
          </TableBody>
        </Table>
      </div>
      )}
      {paginatedRuns.length === 0 ? (
        <EmptyState
          title={t("runs.empty.title")}
          description={t("runs.empty.description")}
          action={
            <Button asChild variant="default" className="mt-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl shadow px-6">
              <Link href="/live">Run your first debate</Link>
            </Button>
          }
        />
      ) : null}
    </div>
  )
}

type SharePopoverLabels = {
  heading: string
  keepPrivate: string
  cancel: string
  apply: string
  error: string
  button: string
}

type SharePopoverProps = {
  currentTeamId?: string | null
  teams: TeamSummary[]
  onAssign: (teamId: string | null) => Promise<void>
  labels: SharePopoverLabels
}

function SharePopover({ currentTeamId, teams, onAssign, labels }: SharePopoverProps) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(currentTeamId ?? "")
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const panelRef = useRef<HTMLDivElement | null>(null)

  useClickOutside(panelRef, () => setOpen(false))

  useEffect(() => {
    if (open) {
      setValue(currentTeamId ?? "")
      setError(null)
    }
  }, [currentTeamId, open])

  const apply = () => {
    startTransition(async () => {
      try {
        await onAssign(value || null)
        setError(null)
        setOpen(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : labels.error)
      }
    })
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label={labels.button}
        onClick={() => setOpen((prev) => !prev)}
      >
        <Share2 className="h-4 w-4" />
      </Button>
      {open ? (
        <div
          ref={panelRef}
          className="absolute right-0 z-20 mt-2 w-64 rounded-2xl border border-stone-200 bg-white p-4 text-left shadow-2xl"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{labels.heading}</p>
          <select
            className="mt-2 w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          >
            <option value="">{labels.keepPrivate}</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name} {team.role ? `(${team.role})` : ""}
              </option>
            ))}
          </select>
          {error ? <p className="mt-2 text-xs text-rose-600">{error}</p> : null}
          <div className="mt-3 flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              {labels.cancel}
            </Button>
            <Button size="sm" onClick={apply} disabled={isPending}>
              {isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
              {labels.apply}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
