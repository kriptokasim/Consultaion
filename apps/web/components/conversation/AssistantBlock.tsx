/**
 * Patchset 76: AssistantBlock component
 * 
 * Groups consecutive assistant messages into a visual block
 * with subtle hover highlight and optional comparison mode.
 */
"use client";

import { cn } from "@/lib/utils";

interface AssistantMessage {
    seat_name?: string;
    content: string;
    type?: string;
    round?: number;
    meta?: Record<string, unknown>;
}

interface AssistantBlockProps {
    /** Messages in this block */
    messages: AssistantMessage[];
    /** Whether comparison mode is active */
    comparisonMode?: boolean;
    /** Active persona for highlighting */
    activePersona?: string;
    /** Additional class names */
    className?: string;
}

export function AssistantBlock({
    messages,
    comparisonMode = false,
    activePersona,
    className,
}: AssistantBlockProps) {
    if (messages.length === 0) return null;

    return (
        <div
            className={cn(
                "space-y-4 p-4 rounded-2xl transition-all duration-200",
                comparisonMode && "border border-transparent hover:border-slate-200 hover:bg-slate-50/50",
                className
            )}
            role="group"
            aria-label="Assistant responses"
        >
            {messages.map((msg, idx) => {
                const isHighlighted = activePersona && msg.seat_name === activePersona;

                return (
                    <div
                        key={idx}
                        className={cn(
                            "flex gap-4 group",
                            isHighlighted && "ring-2 ring-amber-200 ring-offset-2 rounded-xl"
                        )}
                    >
                        {/* Avatar */}
                        <div
                            className={cn(
                                "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center",
                                "text-sm font-bold border shadow-sm transition-all",
                                isHighlighted
                                    ? "bg-amber-100 text-amber-700 border-amber-200"
                                    : "bg-indigo-100 text-indigo-700 border-indigo-200"
                            )}
                            aria-hidden="true"
                        >
                            {msg.seat_name?.[0] || "?"}
                        </div>

                        {/* Message content */}
                        <div
                            className={cn(
                                "flex-1 p-4 rounded-2xl max-w-[85%]",
                                "bg-white border border-slate-200 shadow-sm text-slate-800",
                                "group-hover:shadow-md transition-all"
                            )}
                        >
                            {/* Header */}
                            <div className="flex items-center gap-2 mb-1.5">
                                <span className="text-xs font-bold text-slate-700">
                                    {msg.seat_name || "Assistant"}
                                </span>
                                <span className="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                                    Delegate
                                </span>
                            </div>

                            {/* Content */}
                            <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed">
                                {msg.content}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export default AssistantBlock;
