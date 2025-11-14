"use client"

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import Link from "next/link"
import { Copy, Eye, Loader2, Share2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { ApiError, assignDebateTeam, TeamSummary } from "@/lib/api"

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

type RunsTableProps = {
  items: Run[]
  teams: TeamSummary[]
  profile: { id: string; role: string }
}

const statusVariants: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-900 border-emerald-200",
  running: "bg-amber-50 text-amber-900 border-amber-200",
  failed: "bg-rose-50 text-rose-900 border-rose-200",
  queued: "bg-stone-50 text-stone-900 border-stone-200",
}

const SCOPE_LABELS: Record<Scope, string> = {
  mine: "Mine",
  team: "Team",
  all: "All",
}

function normalizeStatus(status?: string) {
  if (!status) return "queued"
  return statusVariants[status] ? status : "queued"
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

export default function RunsTable({ items, teams, profile }: RunsTableProps) {
  const [scope, setScope] = useState<Scope>(profile.role === "admin" ? "all" : "mine")
  const [rows, setRows] = useState(items)

  useEffect(() => {
    setRows(items)
  }, [items])

  const teamMap = useMemo(() => Object.fromEntries(teams.map((team) => [team.id, team.name])), [teams])

  const availableScopes: Scope[] = profile.role === "admin" ? ["mine", "team", "all"] : ["mine", "team"]

  const filteredRuns = useMemo(() => {
    return rows.filter((run) => {
      if (scope === "all") return true
      if (scope === "mine") {
        return run.user_id === profile.id || !run.user_id
      }
      return Boolean(run.team_id)
    })
  }, [rows, scope, profile.id])

  const paginatedRuns = filteredRuns

  const handleAssignTeam = useCallback(
    async (runId: string, teamId: string | null) => {
      try {
        await assignDebateTeam(runId, teamId)
        setRows((prev) => prev.map((run) => (run.id === runId ? { ...run, team_id: teamId ?? null } : run)))
      } catch (error) {
        if (error instanceof ApiError) {
          const detail = typeof error.body === "object" && error.body?.detail ? error.body.detail : error.message
          throw new Error(detail)
        }
        throw new Error("Unable to update sharing settings")
      }
    },
    [setRows],
  )

  const copyToClipboard = (text: string) => {
    navigator.clipboard?.writeText(text).catch(() => null)
  }

  const truncate = (str: string, length: number) => {
    return str.length > length ? `${str.slice(0, length)}…` : str
  }

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
              {SCOPE_LABELS[option]}
            </button>
          ))}
        </div>
        <p className="text-xs text-stone-500">
          Share a run with a team to make it visible to collaborators.
        </p>
      </div>

      <div className="rounded-3xl border border-stone-200 bg-white shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-stone-100">
              <TableHead className="w-[120px] font-mono text-xs uppercase tracking-wide text-stone-400">Run</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wide text-stone-400">Prompt</TableHead>
              <TableHead className="w-[120px] font-mono text-xs uppercase tracking-wide text-stone-400">Status</TableHead>
              <TableHead className="w-[140px] font-mono text-xs uppercase tracking-wide text-stone-400">Team</TableHead>
              <TableHead className="w-[150px] font-mono text-xs uppercase tracking-wide text-stone-400">Created</TableHead>
              <TableHead className="w-[150px] font-mono text-xs uppercase tracking-wide text-stone-400">Updated</TableHead>
              <TableHead className="w-[140px]" />
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
                      aria-label="Copy run ID"
                      onClick={() => copyToClipboard(run.id)}
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell className="text-sm text-stone-900">{truncate(run.prompt, 80)}</TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "font-mono text-xs capitalize",
                      statusVariants[normalizeStatus(run.status)],
                    )}
                  >
                    {normalizeStatus(run.status)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {run.team_id ? (
                    <Badge className="bg-amber-100 text-amber-900">
                      {teamMap[run.team_id] ?? "Shared"}
                    </Badge>
                  ) : (
                    <span className="text-xs uppercase tracking-wide text-stone-400">Private</span>
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
                    <Link href={`/runs/${run.id}`} className="inline-flex">
                      <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="View run details">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </Link>
                    {teams.length > 0 ? (
                      <SharePopover
                        currentTeamId={run.team_id}
                        teams={teams}
                        onAssign={(teamId) => handleAssignTeam(run.id, teamId)}
                      />
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {paginatedRuns.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-sm text-stone-500">
                  No runs match this filter yet.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

type SharePopoverProps = {
  currentTeamId?: string | null
  teams: TeamSummary[]
  onAssign: (teamId: string | null) => Promise<void>
}

function SharePopover({ currentTeamId, teams, onAssign }: SharePopoverProps) {
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
        setError(err instanceof Error ? err.message : "Unable to share run")
      }
    })
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label="Share to team"
        onClick={() => setOpen((prev) => !prev)}
      >
        <Share2 className="h-4 w-4" />
      </Button>
      {open ? (
        <div
          ref={panelRef}
          className="absolute right-0 z-20 mt-2 w-64 rounded-2xl border border-stone-200 bg-white p-4 text-left shadow-2xl"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Share with team</p>
          <select
            className="mt-2 w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          >
            <option value="">Keep private</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name} {team.role ? `(${team.role})` : ""}
              </option>
            ))}
          </select>
          {error ? <p className="mt-2 text-xs text-rose-600">{error}</p> : null}
          <div className="mt-3 flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={apply} disabled={isPending}>
              {isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
              Apply
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
