import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";
import type { DebateEvent, Role } from "./types";

export interface DebateViewProps {
  events: DebateEvent[];
  className?: string;
}

const getRoleColor = (role?: Role) => {
  if (!role) return "border-l-white/20";
  
  const colors = {
    agent: "border-l-blue-500",
    critic: "border-l-purple-500",
    judge: "border-l-amber-500",
    synthesizer: "border-l-emerald-500",
  };
  return colors[role] || colors.agent;
};

const getTypeBadge = (type: string) => {
  const badges = {
    message: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    score: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    final: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    notice: "bg-white/10 text-white/70 border-white/20",
  };
  return badges[type as keyof typeof badges] || badges.notice;
};

const formatTimestamp = (value?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export default function DebateView({ events, className = "" }: DebateViewProps) {
  return (
    <section 
      className={`py-12 [--parl-blue:#0B1D3A] [--parl-gold:#D4AF37] [--muted:#101827] ${className}`}
      aria-labelledby="debate-title"
    >
      <div className="container mx-auto px-4">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[--parl-gold]/10 rounded-full border border-[--parl-gold]/20 mb-3">
            <MessageSquare className="w-4 h-4 text-[--parl-gold]" aria-hidden="true" />
            <span className="text-sm font-medium text-[--parl-gold]">Live Transcript</span>
          </div>
          <h2 id="debate-title" className="text-3xl md:text-4xl font-bold text-white mb-2">
            Current Debate
          </h2>
        </div>

        <div className="max-w-4xl mx-auto">
          {/* Legend */}
          <div className="mb-6 p-4 bg-[--muted] rounded-lg border border-white/10">
            <h3 className="text-sm font-semibold text-white/70 mb-3">Role Legend</h3>
            <div className="flex flex-wrap gap-3 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full" aria-hidden="true" />
                <span className="text-white/70">Agent</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full" aria-hidden="true" />
                <span className="text-white/70">Critic</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-amber-500 rounded-full" aria-hidden="true" />
                <span className="text-white/70">Judge</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-emerald-500 rounded-full" aria-hidden="true" />
                <span className="text-white/70">Synthesizer</span>
              </div>
            </div>
          </div>

          {/* Events feed */}
          <div 
            className="space-y-4" 
            role="feed" 
            aria-live="polite"
            aria-label="Debate transcript"
          >
            {events.length === 0 ? (
              <Card className="p-8 bg-[--muted] border-white/10 text-center">
                <p className="text-white/60">No events yet. Waiting for debate to start...</p>
              </Card>
            ) : (
              events.map((event, index) => (
                <Card
                  key={index}
                  className={`p-5 bg-[--muted] border-white/10 border-l-4 ${getRoleColor(event.role)} hover:border-white/20 transition-all`}
                  role="article"
                >
                  <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      {event.type === "message" && event.actor && (
                        <h4 className="font-bold text-sm text-white">{event.actor}</h4>
                      )}

                      {event.type === "score" && "judge" in event && (
                        <div className="flex items-center gap-2 text-sm text-white/80">
                          <span className="font-semibold text-white">{event.judge}</span>
                          <span aria-hidden="true" className="text-white/40">→</span>
                          <span className="text-white/70">{event.persona}</span>
                        </div>
                      )}

                      <Badge className={`${getTypeBadge(event.type)} border text-xs`}>
                        {event.type}
                      </Badge>

                      {"round" in event && event.round !== undefined && (
                        <span className="text-xs text-white/50">Round {event.round}</span>
                      )}
                    </div>

                    {formatTimestamp(event.at) && (
                      <time className="text-xs text-white/50" dateTime={event.at}>
                        {formatTimestamp(event.at)}
                      </time>
                    )}
                  </div>

                  {"text" in event && event.text && (
                    <p className="text-sm text-white/80 leading-relaxed mb-3">{event.text}</p>
                  )}

                  {event.type === "score" && (
                    <div className="mt-3 space-y-2 p-3 bg-black/20 rounded border border-white/10 text-xs text-white/80">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white/90">Judge {event.judge}</span>
                        <span className="text-[--parl-gold] font-bold text-sm">{event.score.toFixed(2)}</span>
                      </div>
                      <div className="text-white/70">
                        Target: <span className="font-medium text-white">{event.persona}</span>
                      </div>
                      {event.rationale && (
                        <p className="text-white/60 leading-relaxed">{event.rationale}</p>
                      )}
                    </div>
                  )}
                </Card>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
