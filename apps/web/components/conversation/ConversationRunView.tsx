import React from "react";
import { Bot, User as UserIcon } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";

interface ConversationRunViewProps {
    debate: DebateDetail;
    events: DebateEvent[];
}

export default function ConversationRunView({ debate, events }: ConversationRunViewProps) {
    // Filter down to just the messages spoken by models in the conversation
    const messages = events.filter((e: any) =>
        e.type === "seat_message" ||
        (e.type === "message" && e.seat_name && (e.content || e.text)) ||
        e.type === "conversation_summary"
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
                    <div className="flex items-center justify-center w-full h-32 text-muted-foreground animate-pulse border border-border rounded-xl bg-card">
                        Waiting for conversation to start...
                    </div>
                ) : (
                    messages.map((msg: any, i) => {
                        const isSummary = msg.type === "conversation_summary";
                        const speakerName = isSummary ? "Facilitator Summary" : (msg.seat_name || "Agent");
                        const content = msg.content || msg.text || "";

                        return (
                            <div key={i} className={`flex flex-col border rounded-xl shadow-sm overflow-hidden ${isSummary ? 'border-primary/50 bg-primary/5' : 'border-border bg-card'}`}>
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
                                <div className="p-5 prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                                    {content}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
