"use client"

import { useState } from "react"
import Link from "next/link"
import { Copy, Eye, MoreVertical, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

type RunStatus = "completed" | "running" | "failed" | "pending"

type Run = {
  id: string
  prompt: string
  status: string
  created_at: string
  updated_at: string
}

const statusVariants: Record<RunStatus, string> = {
  completed: "bg-chart-2/10 text-chart-2 border-chart-2/20",
  running: "bg-chart-1/10 text-chart-1 border-chart-1/20",
  failed: "bg-destructive/10 text-destructive border-destructive/20",
  pending: "bg-muted text-muted-foreground border-border",
}

function normalizeStatus(value?: string): RunStatus {
  if (value === "completed" || value === "running" || value === "failed") return value
  return "pending"
}

export default function RunsTable({ items }: { items: Run[] }) {
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10
  const runs = items.map((run) => ({
    ...run,
    status: normalizeStatus(run.status),
  }))
  const totalPages = Math.max(1, Math.ceil(runs.length / itemsPerPage))

  const paginatedRuns = runs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const truncate = (str: string, length: number) => {
    return str.length > length ? str.substring(0, length) + "..." : str
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-b border-border">
              <TableHead className="w-[120px] font-mono text-xs">ID</TableHead>
              <TableHead className="font-mono text-xs">Prompt</TableHead>
              <TableHead className="w-[120px] font-mono text-xs">Status</TableHead>
              <TableHead className="w-[160px] font-mono text-xs">Created</TableHead>
              <TableHead className="w-[160px] font-mono text-xs">Updated</TableHead>
              <TableHead className="w-[80px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedRuns.map((run) => (
              <TableRow key={run.id} className="border-b border-border hover:bg-muted/50">
                <TableCell className="font-mono text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{truncate(run.id, 8)}</span>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(run.id)}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell className="text-sm max-w-md">
                  <span className="text-foreground">{truncate(run.prompt, 80)}</span>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={cn("font-mono text-xs capitalize", statusVariants[run.status])}>
                    {run.status}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {new Date(run.created_at).toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {new Date(run.updated_at).toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <Link href={`/runs/${run.id}`} className="flex items-center gap-2">
                          <Eye className="h-4 w-4" />
                          View Details
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => copyToClipboard(run.id)}>
                        <Copy className="h-4 w-4 mr-2" />
                        Copy ID
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground font-mono">
          Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, runs.length)} of{" "}
          {runs.length} runs
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <Button
                key={page}
                variant={currentPage === page ? "default" : "outline"}
                size="sm"
                className="w-9"
                onClick={() => setCurrentPage(page)}
              >
                {page}
              </Button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
