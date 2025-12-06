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

import { ConversationTimeline } from "@/components/conversation/ConversationTimeline"

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
  mode?: 'debate' | 'conversation'
  truncated?: boolean
  truncateReason?: string | null
}

// ...

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
  mode = 'debate',
  truncated,
  truncateReason,
}: LivePanelProps) {

  const mappedEvents = useMemo(() => {
    return events.map((event) => {
      let title = "Unknown Event"
      let text = ""
      let round = undefined
      let ts = event.at || event.timestamp || new Date().toISOString()
      let data = event

      if (event.type === 'seat_message') {
        title = event.seat_name || "Debater"
        text = event.text
        round = event.round
      } else if (event.type === 'message') {
        title = event.actor || "System"
        text = event.text
        round = event.round
      } else if (event.type === 'round_started') {
        title = `Round ${event.round} Started`
        text = event.topic || ""
        round = event.round
      } else if (event.type === 'score') {
        title = `Score from ${event.judge}`
        text = `${event.persona}: ${event.score}/10 - ${event.rationale}`
      } else if (event.type === 'final') {
        title = "Debate Concluded"
        text = "Final synthesis available."
      }

      return { ...event, title, text, round, ts, data }
    })
  }, [events])

  const getRoundBadgeColor = (round: number) => {
    const colors = [
      "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
      "border-purple-200 bg-purple-50 text-purple-700 dark:border-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
      "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    ]
    return colors[(round - 1) % colors.length] || colors[0]
  }

  return (
    <div className="space-y-6">
      {mode === 'conversation' ? (
        <Card className="border border-amber-200/70 bg-white/95 shadow-[0_18px_36px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
          <CardHeader>
            <CardTitle className="heading-serif text-lg font-semibold text-amber-900 dark:text-amber-50">Conversation Transcript</CardTitle>
          </CardHeader>
          <CardContent>
            <ConversationTimeline
              events={events}
              activePersona={activePersona}
              truncated={truncated}
              truncateReason={truncateReason}
            />
          </CardContent>
        </Card>
      ) : (
        (mappedEvents.length > 0 || loading) && (
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
        )
      )}
    </div>
  )
}
