"use client"

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import Link from "next/link"
import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { Copy, Eye, Loader2, Share2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { ApiError, assignDebateTeam, TeamSummary, getDebates } from "@/lib/api"
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
  profile: { id: string; role: string }
  initialQuery?: string
  initialStatus?: string | null
}

function normalizeStatus(status?: string) {
  if (!status) return "queued"
  return status
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

export default function RunsTable({ items, teams, profile, initialQuery = "", initialStatus = null }: RunsTableProps) {
  const { t } = useI18n()
  const [scope, setScope] = useState<Scope>(profile.role === "admin" ? "all" : "mine")
  const [rows, setRows] = useState(items)
  const [search, setSearch] = useState(initialQuery)
  const [statusFilter, setStatusFilter] = useState<string | null>(initialStatus)
  const debouncedSearch = useDebounce(search, 300)
  const { pushToast } = useToast()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const searchParamsString = searchParams?.toString() || ""
  const [searchLoading, setSearchLoading] = useState(false)

  useEffect(() => {
    if (debouncedSearch || statusFilter) return
    setRows(items)
  }, [items, debouncedSearch, statusFilter])

  const teamMap = useMemo(() => Object.fromEntries(teams.map((team) => [team.id, team.name])), [teams])

  const availableScopes: Scope[] = profile.role === "admin" ? ["mine", "team", "all"] : ["mine", "team"]

  const filteredRuns = useMemo(() => {
    const lowerQuery = debouncedSearch.trim().toLowerCase()
    return rows.filter((run) => {
      if (scope === "mine" && run.user_id !== profile.id && run.user_id) return false
      if (scope === "team" && !run.team_id) return false
      if (statusFilter && run.status !== statusFilter) return false
      if (lowerQuery && !`${run.id} ${run.prompt}`.toLowerCase().includes(lowerQuery)) return false
      return true
    })
  }, [rows, scope, profile.id, debouncedSearch, statusFilter])

  const paginatedRuns = filteredRuns

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
      { auth: false },
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
  }, [debouncedSearch, statusFilter, pushToast])

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
              onClick={() => setScope(option)}
              >
              {t(SCOPE_KEYS[option])}
            </button>
          ))}
        </div>
        <p className="text-xs text-stone-500">{t("runs.scope.note")}</p>
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
            {paginatedRuns.map((run) => (
              <TableRow key={run.id} className="border-b border-stone-50 hover:bg-amber-50/40">
                <TableCell className="font-mono text-xs text-stone-600">
                  <div className="flex items-center gap-2">
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
                  <StatusBadge status={normalizeStatus(run.status)} />
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
                      <Link href={`/debates/${run.id}/replay`} className="text-xs font-semibold text-amber-700 underline-offset-4 hover:underline">
                        {t("dashboard.recentDebates.replay")}
                      </Link>
                    ) : null}
                    <Link href={`/runs/${run.id}`} className="inline-flex">
                      <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={t("runs.table.view")}>
                        <Eye className="h-4 w-4" />
                      </Button>
                    </Link>
                    {teams.length > 0 ? (
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
            ))}
          </TableBody>
        </Table>
      </div>
      {paginatedRuns.length === 0 ? (
        <EmptyState
          title={t("runs.empty.title")}
          description={t("runs.empty.description")}
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
