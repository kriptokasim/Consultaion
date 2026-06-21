import React, { useRef, useEffect } from 'react';
import { Terminal, CheckCircle2, AlertCircle, Clock, GitCommit } from 'lucide-react';

export interface TimelineEvent {
  id: string;
  type: string;
  timestamp: string;
  label: string;
  message?: string;
  details?: string;
  status?: 'info' | 'success' | 'warning' | 'error';
  lane?: string;
}

export type RunEvent = TimelineEvent;

export function EventTimeline({ events, isRunning }: { events: TimelineEvent[], isRunning: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isRunning && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, isRunning]);

  const getIcon = (status: TimelineEvent['status']) => {
    switch (status) {
      case 'success': return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'warning': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />;
      default: return <Terminal className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-card rounded-lg border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/30 flex items-center gap-2">
        <Clock className="w-4 h-4 text-muted-foreground" />
        <h3 className="font-medium text-sm">Execution Trace</h3>
      </div>
      
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-6">
        {events.length === 0 ? (
          <div className="text-sm text-muted-foreground italic text-center py-8">
            Awaiting events...
          </div>
        ) : (
          <div className="relative border-l border-muted ml-3 space-y-6">
            {events.map((event) => (
              <div key={event.id} className="relative pl-6">
                <span className="absolute -left-2.5 top-0.5 bg-background p-0.5 rounded-full border border-muted shadow-sm">
                  {getIcon(event.status)}
                </span>
                
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold">{event.label}</span>
                    <span className="text-[10px] text-muted-foreground tabular-nums">
                      {new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' })}
                    </span>
                    {event.lane && (
                      <span className="text-[10px] bg-muted px-1.5 rounded-sm font-mono uppercase">
                        {event.lane}
                      </span>
                    )}
                  </div>
                  
                  {event.details && (
                    <div className="text-xs text-muted-foreground mt-1 bg-muted/30 p-2 rounded border font-mono whitespace-pre-wrap break-all">
                      {event.details}
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {isRunning && (
              <div className="relative pl-6 pb-2">
                <span className="absolute -left-2.5 top-0.5 bg-background p-0.5 rounded-full border border-muted shadow-sm animate-pulse">
                  <Terminal className="w-4 h-4 text-muted-foreground" />
                </span>
                <span className="text-xs text-muted-foreground italic animate-pulse">Listening...</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
