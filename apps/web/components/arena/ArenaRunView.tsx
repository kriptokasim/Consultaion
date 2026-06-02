import React from "react";
import { Bot, Zap } from "lucide-react";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";

interface ArenaRunViewProps {
  debate: DebateDetail;
  events: DebateEvent[];
}

export default function ArenaRunView({ debate, events }: ArenaRunViewProps) {
  const safeEvents = events || [];

  const modelReplies = safeEvents.filter(
    (e: any) =>
      e.type === "seat_message" &&
      (e.content || e.text) &&
      e.seat_id !== "synthesizer",
  );

  const synthesizerReply = safeEvents.find(
    (e: any) => e.type === "seat_message" && e.seat_id === "synthesizer",
  );

  return (
    <div className="flex flex-col h-full gap-6 overflow-y-auto pb-10">
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm shrink-0">
        <h2 className="text-xl font-semibold mb-2 text-foreground">Prompt</h2>
        <p className="text-muted-foreground whitespace-pre-wrap">
          {debate.prompt}
        </p>
      </div>

      {/* Synthesizer result prominent at top if exists */}
      {synthesizerReply ? (
        <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 shadow-sm shrink-0">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-primary/20 rounded-lg text-primary">
              <Zap className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-foreground">
              Synthesized Best Answer
            </h2>
          </div>
          <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
            {synthesizerReply.content || synthesizerReply.text || ""}
          </div>
        </div>
      ) : null}

      <div className="overflow-x-auto pb-4 custom-scrollbar shrink-0 h-[500px]">
        <div className="flex gap-4 min-w-max h-full">
          {modelReplies.length === 0
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="flex flex-col w-[450px] border border-border bg-card rounded-xl shadow-sm overflow-hidden flex-shrink-0 max-h-full opacity-50"
                >
                  <div className="bg-secondary/50 p-4 border-b border-border flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                      <div className="h-9 w-9 rounded-lg bg-primary/10 animate-pulse" />
                      <div className="h-4 w-24 bg-muted animate-pulse rounded" />
                    </div>
                    <div className="h-3 w-16 bg-muted animate-pulse rounded" />
                  </div>
                  <div className="p-5 space-y-2">
                    <div className="h-4 w-full bg-muted animate-pulse rounded" />
                    <div className="h-4 w-5/6 bg-muted animate-pulse rounded" />
                    <div className="h-4 w-4/6 bg-muted animate-pulse rounded" />
                  </div>
                </div>
              ))
            : modelReplies.map((reply: any, i: number) => (
                <div
                  key={i}
                  className="flex flex-col w-[450px] border border-border bg-card rounded-xl shadow-sm overflow-hidden flex-shrink-0 max-h-full"
                >
                  <div className="bg-secondary/50 p-4 border-b border-border flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                      <div className="p-2 bg-primary/10 rounded-lg text-primary">
                        <Bot className="w-5 h-5" />
                      </div>
                      <div
                        className="font-semibold text-foreground text-sm truncate max-w-[200px]"
                        title={reply.seat_name}
                      >
                        {reply.seat_name || "Agent"}
                      </div>
                    </div>
                    <div
                      className="text-xs text-muted-foreground ml-2 truncate max-w-[120px]"
                      title={reply.model}
                    >
                      {reply.model?.split("/").pop() || "Model"}
                    </div>
                  </div>
                  <div className="p-5 overflow-y-auto flex-1 prose prose-sm dark:prose-invert max-w-none custom-scrollbar whitespace-pre-wrap">
                    {reply.content || reply.text || ""}
                  </div>
                </div>
              ))}
        </div>
      </div>
    </div>
  );
}
