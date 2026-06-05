import React from "react";
import { Bot, User as UserIcon } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";
import { sanitizeMarkdown } from "@/lib/sanitize";

interface ConversationRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
}

export default function ConversationRunView({ debate, events }: ConversationRunViewProps) {
    // Filter down to messages that carry text content
    const messages = events.filter((e: any) =>
        (e.type === "seat_message" && (e.content || e.text)) ||
        (e.type === "message" && (e.text || e.content)) ||
        e.type === "conversation_summary" ||
        e.type === "final"
    );

    return (
        <div className="flex flex-col h-full gap-6 max-w-4xl mx-auto">
            <div className="bg-card border border-border rounded-xl p-6 shadow-sm shrink-0">
                <h2 className="text-xl font-semibold mb-2 text-foreground flex items-center gap-2">
                    <UserIcon className="w-5 h-5" /> Prompt
                </h2>
                <div className="text-muted-foreground whitespace-pre-wrap prose prose-sm dark:prose-invert max-w-none">
                    {debate.prompt}
                </div>
            </div>

            <div className="flex-1 flex flex-col gap-4 overflow-y-auto pb-8 custom-scrollbar">
                {messages.length === 0 ? (
                    <div className="flex flex-col border border-border rounded-xl bg-card shadow-sm opacity-50">
                        <div className="p-3 border-b border-border bg-secondary/50 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className="h-6 w-6 rounded-lg bg-primary/10 animate-pulse" />
                                <div className="h-4 w-24 bg-muted animate-pulse rounded" />
                            </div>
                        </div>
                        <div className="p-5 space-y-2">
                            <div className="h-4 w-full bg-muted animate-pulse rounded" />
                            <div className="h-4 w-5/6 bg-muted animate-pulse rounded" />
                            <div className="h-4 w-4/6 bg-muted animate-pulse rounded" />
                        </div>
                    </div>
                ) : (
                    messages.map((msg: any, i) => {
                        const isSummary = msg.type === "conversation_summary" || msg.type === "final";
                        const speakerName = isSummary ? "Facilitator Summary" : (msg.seat_name || msg.actor || "Agent");
                        const content = msg.content || msg.text || "";

                        return (
                            <div key={i} className={`flex flex-col border rounded-xl shadow-sm overflow-hidden shrink-0 ${isSummary ? 'border-primary/50 bg-primary/5' : 'border-border bg-card'}`}>
                                <div className={`p-3 border-b flex items-center justify-between shrink-0 ${isSummary ? 'bg-primary/10 border-primary/20' : 'bg-secondary/50 border-border'}`}>
                                    <div className="flex items-center gap-2">
                                        <div className={`p-1.5 rounded-lg ${isSummary ? 'bg-primary/20 text-primary' : 'bg-primary/10 text-primary'}`}>
                                            <Bot className="w-4 h-4" />
                                        </div>
                                        <div className="font-semibold text-foreground text-sm">
                                            {speakerName}
                                        </div>
                                    </div>
                                    {msg.model && (
                                        <div className="text-xs text-muted-foreground ml-2">
                                            {msg.model.split('/').pop()}
                                        </div>
                                    )}
                                </div>
                                <div 
                                    className="p-5 prose prose-sm dark:prose-invert max-w-none"
                                    dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(content) }}
                                />
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
