import React from "react";
import { Bot } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";


interface CompareRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
}

export default function CompareRunView({ debate, events }: CompareRunViewProps) {
    // Hydration events come from REST as e.text, live SSE events drop as reply.content
    const modelReplies = events.filter((e: any) =>
        (e.type === "seat_message" && e.mode === "compare") ||
        (e.seat_name && (e.content || e.text) && debate.mode === "compare")
    );

    return (
        <div className="flex flex-col h-full gap-6">
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm shrink-0">
                <h2 className="text-xl font-semibold mb-2 text-foreground">Prompt</h2>
                <p className="text-muted-foreground whitespace-pre-wrap">{debate.prompt}</p>
            </div>

            <div className="flex-1 overflow-x-auto pb-4 custom-scrollbar">
                <div className="flex gap-4 min-w-max h-full">
                    {modelReplies.length === 0 ? (
                        <div className="flex items-center justify-center w-full h-32 text-muted-foreground animate-pulse">
                            Waiting for models to respond...
                        </div>
                    ) : (
                        modelReplies.map((reply: any, i) => (
                            <div key={i} className="flex flex-col w-[450px] border border-border bg-card rounded-xl shadow-sm overflow-hidden flex-shrink-0 max-h-full">
                                <div className="bg-secondary/50 p-4 border-b border-border flex items-center justify-between shrink-0">
                                    <div className="flex items-center gap-2">
                                        <div className="p-2 bg-primary/10 rounded-lg text-primary">
                                            <Bot className="w-5 h-5" />
                                        </div>
                                        <div className="font-semibold text-foreground text-sm truncate max-w-[200px]" title={reply.seat_name}>
                                            {reply.seat_name || "Agent"}
                                        </div>
                                    </div>
                                    <div className="text-xs text-muted-foreground ml-2 truncate max-w-[120px]" title={reply.model}>
                                        {reply.model?.split('/').pop() || "Model"}
                                    </div>
                                </div>
                                <div className="p-5 overflow-y-auto flex-1 prose prose-sm dark:prose-invert max-w-none custom-scrollbar whitespace-pre-wrap">
                                    {reply.content || reply.text || ""}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
