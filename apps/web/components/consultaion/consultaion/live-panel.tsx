"use client"

import { useMemo } from "react"
import { PlayCircle, Loader2, FileJson, StopCircle, Timer, UsersRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import ValidatedTextarea from "@/components/ui/validated-textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts"

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

  useKeyboardShortcuts(
    [
      {
        combo: "ctrl+enter",
        handler: () => {
          if (!disabled) {
            onStart()
          }
        },
        enabled: !running,
      },
    ],
    [disabled, running, onStart],
  )

  return (
    <div className="space-y-6">
      <Card className="border border-amber-200/70 bg-gradient-to-br from-amber-50/90 via-white to-amber-50/70 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/60 dark:from-[#7b5b40] dark:via-[#4f3727] dark:to-[#38261a]">
        <CardHeader>
          <CardTitle className="heading-serif text-2xl font-semibold text-amber-900 dark:text-amber-50">Start New Debate</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ValidatedTextarea
            placeholder="Enter your debate prompt or question..."
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            minLength={10}
            maxLength={5000}
            aria-label="Debate prompt"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="font-mono text-sm text-amber-800 dark:text-amber-200">{prompt.length} characters</div>
            <div className="flex items-center gap-2">
              {running && (
                <Button variant="ghost" className="gap-2 text-amber-800 dark:text-amber-100" onClick={onStop}>
                  <StopCircle className="h-4 w-4" />
                  Stop
                </Button>
              )}
              <Button
                onClick={onStart}
                disabled={disabled}
                aria-busy={running}
                aria-disabled={disabled}
                className="gap-2 rounded-full shadow-[0_16px_30px_rgba(255,190,92,0.35)]"
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
            <Card className="border border-amber-200/70 bg-white/90 shadow-[0_12px_24px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                  <UsersRound className="h-4 w-4 text-amber-700" />
                  Active Speaker
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-baseline justify-between">
                <div className="text-lg font-semibold text-amber-900 dark:text-amber-50">{activePersona}</div>
                <div className="flex items-center gap-2 text-sm text-amber-800 dark:text-amber-100">
                  <Timer className="h-4 w-4 text-amber-600" />
                  {speakerTime}s
                </div>
              </CardContent>
            </Card>
          )}
          {vote?.ranking?.length ? (
            <Card className="border border-amber-200/70 bg-white/90 shadow-[0_12px_24px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-amber-900 dark:text-amber-50">Current Ranking</CardTitle>
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
        <Card className="border border-amber-200/70 bg-white/95 shadow-[0_18px_36px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
          <CardHeader>
            <CardTitle className="heading-serif text-lg font-semibold text-amber-900 dark:text-amber-50">Live Stream</CardTitle>
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
                        className="flex animate-pulse items-start gap-3 rounded-lg border border-amber-100 bg-amber-50/70 p-4"
                      >
                        <div className="h-6 w-12 rounded-full bg-amber-100/80" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 w-1/2 rounded bg-amber-100/80" />
                          <div className="h-3 w-3/4 rounded bg-amber-100/80" />
                          <div className="h-3 w-1/3 rounded bg-amber-100/80" />
                        </div>
                        <div className="h-8 w-8 rounded-full bg-amber-100/80" />
                      </div>
                    ))
                  : null}
                {mappedEvents.map((event, index) => (
                  <div
                    key={`${event.type}-${index}`}
                    className="flex items-start gap-3 rounded-lg border border-amber-100 bg-amber-50/70 p-4 transition-colors hover:bg-white hover:shadow-md dark:border-amber-900/40 dark:bg-amber-950/20"
                  >
                    {event.round && (
                      <Badge variant="outline" className={`${getRoundBadgeColor(event.round)} font-mono text-xs`}>
                        R{event.round}
                      </Badge>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="mb-1 text-sm font-semibold text-amber-900 dark:text-amber-50">{event.title}</div>
                      <p className="text-sm text-amber-900/80 dark:text-amber-50/70 line-clamp-2">{event.text}</p>
                      {event.ts && (
                        <div className="mt-2 font-mono text-xs text-amber-700 dark:text-amber-100/70">
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
