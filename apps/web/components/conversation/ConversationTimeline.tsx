import { cn } from "@/lib/utils"
import { useMemo } from "react"

interface ConversationTimelineProps {
    events: any[]
    activePersona?: string
}

export function ConversationTimeline({ events, activePersona }: ConversationTimelineProps) {
    const rounds = useMemo(() => {
        const grouped: Record<number, any[]> = {}
        events.forEach(event => {
            if (event.type !== 'seat_message' && event.type !== 'conversation_summary' && event.type !== 'message') return
            const round = event.round ?? 0
            if (!grouped[round]) grouped[round] = []
            grouped[round].push(event)
        })
        return grouped
    }, [events])

    return (
        <div className="space-y-8">
            {Object.entries(rounds).map(([round, messages]) => (
                <div key={round} className="space-y-4">
                    <div className="flex items-center gap-4">
                        <div className="h-px flex-1 bg-slate-200" />
                        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Round {round}</span>
                        <div className="h-px flex-1 bg-slate-200" />
                    </div>

                    <div className="space-y-6">
                        {messages.map((msg, idx) => {
                            const isScribe = msg.type === 'conversation_summary' || msg.seat_name === 'Scribe'
                            return (
                                <div key={idx} className={cn("flex gap-4", isScribe ? "justify-center" : "")}>
                                    {!isScribe && (
                                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-bold border border-indigo-200">
                                            {msg.seat_name?.[0] || '?'}
                                        </div>
                                    )}

                                    <div className={cn(
                                        "p-4 rounded-2xl max-w-[85%]",
                                        isScribe
                                            ? "bg-amber-50 border border-amber-100 text-amber-900 w-full text-center italic"
                                            : "bg-white border border-slate-200 shadow-sm text-slate-800"
                                    )}>
                                        {!isScribe && <div className="text-xs font-semibold text-slate-500 mb-1">{msg.seat_name}</div>}
                                        <div className="prose prose-sm max-w-none whitespace-pre-wrap">
                                            {msg.content}
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            ))}
        </div>
    )
}
