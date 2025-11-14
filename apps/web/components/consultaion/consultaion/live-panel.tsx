"use client"

import { useMemo } from "react"
import { PlayCircle, Loader2, FileJson, StopCircle, Timer, UsersRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"

type LivePanelProps = {
  prompt: string
  onPromptChange: (value: string) => void
  onStart: () => void | Promise<void>
  onStop: () => void
  running: boolean
  events: any[]
  activePersona?: string
  speakerTime: number
  vote?: { method?: string; ranking?: string[] }
  loading?: boolean
}

type EventRow = {
  type: string
  round?: number
  title: string
  text: string
  ts?: string
  data: any
}

const roundColors = [
  "bg-amber-50 text-amber-700 border-amber-100",
  "bg-emerald-50 text-emerald-700 border-emerald-100",
  "bg-blue-50 text-blue-700 border-blue-100",
  "bg-rose-50 text-rose-700 border-rose-100",
]

function toEventRow(event: any): EventRow {
  const ts = event.ts ?? event.timestamp ?? new Date().toISOString()
  switch (event.type) {
    case "round_started":
      return {
        type: "round",
        round: event.round,
        title: `Round ${event.round ?? ""} started`,
        text: event.note ?? "New round kicked off",
        ts,
        data: event,
      }
    case "message":
      return {
        type: "message",
        round: event.round,
        title: event.revised ? "Revision Update" : "Candidate Draft",
        text: event.revised ? "Agents are revising their drafts" : "Agents produced initial drafts",
        ts,
        data: event,
      }
    case "score":
      return {
        type: "score",
        round: event.round,
        title: "Judges submitted scores",
        text: "Aggregated scores are available",
        ts,
        data: event,
      }
    case "final":
      return {
        type: "final",
        title: "Synthesis complete",
        text: "Final answer is ready",
        ts,
        data: event,
      }
    default:
      return {
        type: event.type ?? "event",
        title: event.type?.toString() ?? "Event",
        text: "Received new event",
        ts,
        data: event,
      }
  }
}

export default function LivePanel({
  prompt,
  onPromptChange,
  onStart,
  onStop,
  running,
  events,
  activePersona,
  speakerTime,
  vote,
  loading = false,
}: LivePanelProps) {
  const mappedEvents = useMemo(() => events.map(toEventRow), [events])

  const getRoundBadgeColor = (round?: number) => {
    if (!round) return "bg-stone-100 text-stone-500 border-stone-200"
    return roundColors[(round - 1) % roundColors.length]
  }

  const disabled = !prompt.trim() || running

  return (
    <div className="space-y-6">
      <Card className="border border-stone-200 bg-white">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-stone-900">Start New Debate</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            placeholder="Enter your debate prompt or question..."
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            className="min-h-32 resize-none border-stone-200 focus-visible:ring-amber-500"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="font-mono text-sm text-stone-500">{prompt.length} characters</div>
            <div className="flex items-center gap-2">
              {running && (
                <Button variant="ghost" className="gap-2 text-amber-700" onClick={onStop}>
                  <StopCircle className="h-4 w-4" />
                  Stop
                </Button>
              )}
              <Button
                onClick={onStart}
                disabled={disabled}
                className="gap-2 rounded-full bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50"
              >
                {running ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <PlayCircle className="h-4 w-4" />
                    Run Debate
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {(activePersona || vote?.ranking?.length) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {activePersona && (
            <Card className="border border-stone-200 bg-white">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                  <UsersRound className="h-4 w-4" />
                  Active Speaker
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-baseline justify-between">
                <div className="text-lg font-semibold text-stone-900">{activePersona}</div>
                <div className="flex items-center gap-2 text-sm text-stone-500">
                  <Timer className="h-4 w-4" />
                  {speakerTime}s
                </div>
              </CardContent>
            </Card>
          )}
          {vote?.ranking?.length ? (
            <Card className="border border-stone-200 bg-white">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-stone-800">Current Ranking</CardTitle>
              </CardHeader>
              <CardContent className="flex gap-2">
                {vote.ranking.slice(0, 3).map((persona, idx) => (
                  <Badge
                    key={persona}
                    variant="outline"
                    className="font-mono text-xs border-amber-200 bg-amber-50 text-amber-700"
                  >
                    #{idx + 1} {persona}
                  </Badge>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      )}

      {(mappedEvents.length > 0 || loading) && (
        <Card className="border border-stone-200 bg-white">
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-stone-900">Live Stream</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-96">
              <div
                className="space-y-3"
                role="feed"
                aria-live="polite"
                aria-busy={loading && mappedEvents.length === 0}
              >
                {loading && mappedEvents.length === 0
                  ? Array.from({ length: 3 }).map((_, idx) => (
                      <div
                        key={`skeleton-${idx}`}
                        className="flex animate-pulse items-start gap-3 rounded-lg border border-stone-100 bg-stone-50 p-4"
                      >
                        <div className="h-6 w-12 rounded-full bg-stone-100" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 w-1/2 rounded bg-stone-100" />
                          <div className="h-3 w-3/4 rounded bg-stone-100" />
                          <div className="h-3 w-1/3 rounded bg-stone-100" />
                        </div>
                        <div className="h-8 w-8 rounded-full bg-stone-100" />
                      </div>
                    ))
                  : null}
                {mappedEvents.map((event, index) => (
                  <div
                    key={`${event.type}-${index}`}
                    className="flex items-start gap-3 rounded-lg border border-stone-100 bg-stone-50/70 p-4 transition-colors hover:bg-white"
                  >
                    {event.round && (
                      <Badge variant="outline" className={`${getRoundBadgeColor(event.round)} font-mono text-xs`}>
                        R{event.round}
                      </Badge>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm mb-1">{event.title}</div>
                      <p className="text-sm text-muted-foreground line-clamp-2">{event.text}</p>
                      {event.ts && (
                        <div className="text-xs text-muted-foreground font-mono mt-2">
                          {new Date(event.ts).toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                    <Sheet>
                      <SheetTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" aria-label="View event JSON">
                          <FileJson className="h-4 w-4" />
                        </Button>
                      </SheetTrigger>
                      <SheetContent className="w-full sm:max-w-xl">
                        <SheetHeader>
                          <SheetTitle>Event Data</SheetTitle>
                          <SheetDescription>Raw payload from the orchestrator</SheetDescription>
                        </SheetHeader>
                    <ScrollArea className="mt-6 h-full">
                      <pre className="overflow-x-auto rounded-lg bg-stone-900 p-4 font-mono text-xs text-amber-200">
                            {JSON.stringify(event.data, null, 2)}
                          </pre>
                        </ScrollArea>
                      </SheetContent>
                    </Sheet>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
