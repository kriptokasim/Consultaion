"use client"

import { useMemo } from "react"
import { Copy, Share, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

type ScoreRow = {
  persona: string
  score: number
  rationale?: string
  judge?: string
}

type VoteSummary = {
  method: string
  ranking: string[]
  weights?: Record<string, number>
}

type RoundMeta = {
  type: "draft" | "critique" | "judge" | "final"
  timestamp: string
  note: string
}

type RunDetailProps = {
  debate: any
  report: any
}

function classifyRound(label?: string) {
  const normalized = (label ?? "").toLowerCase()
  if (normalized.includes("draft")) return "draft"
  if (normalized.includes("critique")) return "critique"
  if (normalized.includes("judge")) return "judge"
  return "final"
}

function FinalAnswerCard({ answer }: { answer: string }) {
  const copyToClipboard = () => navigator.clipboard.writeText(answer)
  return (
    <Card className="border-border">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-lg font-semibold">Final Answer</CardTitle>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={copyToClipboard} aria-label="Copy answer">
            <Copy className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Share answer">
            <Share className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Download answer">
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">{answer}</p>
      </CardContent>
    </Card>
  )
}

function Scoreboard({ scores }: { scores: ScoreRow[] }) {
  const personas = Array.from(new Set(scores.map((score) => score.persona)))
  const maxScore = 10

  const averages = useMemo(() => {
    return personas.reduce<Record<string, number>>((acc, persona) => {
      const personaScores = scores.filter((score) => score.persona === persona)
      const avg = personaScores.reduce((sum, entry) => sum + entry.score, 0) / Math.max(1, personaScores.length)
      acc[persona] = avg
      return acc
    }, {})
  }, [scores, personas])

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Scoreboard</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {personas.map((persona) => (
          <div key={persona} className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold">{persona}</div>
                <div className="text-xs text-muted-foreground">Avg {averages[persona].toFixed(1)}/10</div>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                {averages[persona].toFixed(1)}
              </Badge>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {scores
                .filter((entry) => entry.persona === persona)
                .map((entry, idx) => {
                  const intensity = entry.score / maxScore
                  return (
                    <TooltipProvider key={`${entry.persona}-${idx}`}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div
                            className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
                            style={{
                              backgroundColor: `oklch(from var(--chart-1) calc(l + ${
                                (1 - intensity) * 0.2
                              }) c h / ${0.15 + intensity * 0.25})`,
                            }}
                          >
                            <div className="font-medium">{entry.judge ?? 'Judge'}</div>
                            <div className="font-mono text-xs">{entry.score.toFixed(1)}</div>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs font-mono">{entry.rationale || 'No rationale provided'}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )
                })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function VoteRibbon({ voteSummary }: { voteSummary: VoteSummary[] }) {
  if (!voteSummary.length) return null
  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Vote Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {voteSummary.map((vote, idx) => (
          <div key={`vote-${idx}`} className="space-y-2">
            <Badge variant="outline" className="font-mono text-xs">
              {vote.method.toUpperCase()}
            </Badge>
            <div className="flex flex-wrap gap-3">
              {vote.ranking.slice(0, 3).map((persona, rankIdx) => (
                <div
                  key={`${persona}-${rankIdx}`}
                  className="flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-4 py-2"
                >
                  <span className="text-2xl font-bold text-muted-foreground">#{rankIdx + 1}</span>
                  <div>
                    <div className="text-sm font-semibold">{persona}</div>
                    {vote.weights && vote.weights[persona] !== undefined && (
                      <div className="text-xs text-muted-foreground font-mono">
                        weight {vote.weights[persona].toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function RoundsTimeline({ rounds }: { rounds: RoundMeta[] }) {
  if (!rounds.length) return null
  const icons: Record<RoundMeta["type"], string> = {
    draft: "📝",
    critique: "🔍",
    judge: "⚖️",
    final: "✅",
  }
  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Rounds Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {rounds.map((round, index) => (
            <div key={`${round.type}-${index}`} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <span>{icons[round.type]}</span>
                </div>
                {index < rounds.length - 1 && <div className="h-full w-px bg-border mt-2" />}
              </div>
              <div className="flex-1 pb-4">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="font-mono text-xs capitalize">
                    {round.type}
                  </Badge>
                  <span className="text-xs text-muted-foreground font-mono">
                    {new Date(round.timestamp).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <p className="text-sm text-foreground">{round.note}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default function RunDetail({ debate, report }: RunDetailProps) {
  const finalAnswer = (debate?.final_content ?? report?.final ?? "").trim() || "Pending synthesis..."
  const scoreRows: ScoreRow[] = Array.isArray(report?.scores)
    ? report.scores.map((score: any) => ({
        persona: score.persona ?? "Agent",
        score: typeof score.score === "number" ? score.score : Number(score.score ?? 0),
        rationale: score.rationale,
        judge: score.judge,
      }))
    : []

  const rounds: RoundMeta[] = Array.isArray(report?.rounds)
    ? report.rounds
        .map((round: any) => ({
          type: classifyRound(round.label ?? round.note),
          timestamp: round.started_at ?? round.created_at ?? new Date().toISOString(),
          note: round.note ?? round.label ?? "",
        }))
        .sort((a: RoundMeta, b: RoundMeta) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    : []

  const voteSummary: VoteSummary[] = useMemo(() => {
    const ranking = debate?.final_meta?.ranking ?? []
    if (!ranking.length) return []
    return [
      {
        method: debate?.final_meta?.vote?.method ?? "borda",
        ranking,
        weights: debate?.final_meta?.vote?.result?.combined,
      },
    ]
  }, [debate])

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-xs font-mono text-muted-foreground uppercase tracking-wide">Prompt</p>
        <Card className="border-border">
          <CardContent className="p-4">
            <p className="text-sm leading-relaxed text-foreground">{debate?.prompt}</p>
            <div className="mt-3 text-xs text-muted-foreground font-mono flex flex-wrap gap-3">
              <span>Status: {debate?.status}</span>
              {debate?.created_at && <span>Created {new Date(debate.created_at).toLocaleString()}</span>}
            </div>
          </CardContent>
        </Card>
      </div>

      <FinalAnswerCard answer={finalAnswer} />
      {scoreRows.length ? <Scoreboard scores={scoreRows} /> : null}
      <VoteRibbon voteSummary={voteSummary} />
      <RoundsTimeline rounds={rounds} />
    </div>
  )
}
