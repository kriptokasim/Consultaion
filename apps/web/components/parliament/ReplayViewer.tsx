"use client";

import React, { useState, useEffect, useRef } from "react";
import { useDebateTimeline } from "../../lib/hooks/useDebateTimeline";
import { DebateTimelineEvent } from "../../lib/api/debates";
import { format } from "date-fns";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { Play, Pause, SkipBack, SkipForward, AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";

interface ReplayViewerProps {
    debateId: string;
}

export function ReplayViewer({ debateId }: ReplayViewerProps) {
    const { data: events, loading, error } = useDebateTimeline(debateId);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isPlaying && events && currentIndex < events.length - 1) {
            interval = setInterval(() => {
                setCurrentIndex((prev) => prev + 1);
            }, 2000); // 2 seconds per event
        } else if (currentIndex >= (events?.length || 0) - 1) {
            setIsPlaying(false);
        }
        return () => clearInterval(interval);
    }, [isPlaying, currentIndex, events]);

    useEffect(() => {
        if (scrollRef.current) {
            const activeElement = scrollRef.current.querySelector(`[data-index="${currentIndex}"]`);
            if (activeElement) {
                activeElement.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }, [currentIndex]);

    if (loading) {
        return <div className="p-8 text-center text-muted-foreground">Loading replay...</div>;
    }

    if (error) {
        return (
            <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>Failed to load debate timeline.</AlertDescription>
            </Alert>
        );
    }

    if (!events || events.length === 0) {
        return <div className="p-8 text-center text-muted-foreground">No events found.</div>;
    }

    const currentEvent = events[currentIndex];

    return (
        <div className="flex flex-col h-[600px] border rounded-lg overflow-hidden bg-background">
            <div className="flex items-center justify-between p-4 border-b bg-muted/50">
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setCurrentIndex(0)}
                        disabled={currentIndex === 0}
                    >
                        <SkipBack className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setIsPlaying(!isPlaying)}
                    >
                        {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setCurrentIndex(events.length - 1)}
                        disabled={currentIndex === events.length - 1}
                    >
                        <SkipForward className="h-4 w-4" />
                    </Button>
                </div>
                <div className="text-sm text-muted-foreground">
                    Event {currentIndex + 1} of {events.length}
                </div>
            </div>

            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-4">
                    {events.map((event, index) => (
                        <TimelineItem
                            key={event.event_id}
                            event={event}
                            isActive={index === currentIndex}
                            isPast={index < currentIndex}
                            index={index}
                        />
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}

function TimelineItem({ event, isActive, isPast, index }: { event: DebateTimelineEvent; isActive: boolean; isPast: boolean; index: number }) {
    const isSystem = event.type === "system_notice" || event.type === "round_start" || event.type === "round_end" || event.type === "debate_completed" || event.type === "debate_failed";

    return (
        <div
            data-index={index}
            className={cn(
                "transition-opacity duration-500",
                isActive ? "opacity-100" : isPast ? "opacity-50" : "opacity-30"
            )}
        >
            {isSystem ? (
                <div className="flex justify-center my-4">
                    <Badge variant="outline" className="text-xs text-muted-foreground">
                        {event.content}
                    </Badge>
                </div>
            ) : (
                <div className={cn(
                    "flex flex-col gap-1 p-3 rounded-lg border",
                    event.role === "critic" ? "bg-destructive/10 border-destructive/20" : "bg-card"
                )}>
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-sm">{event.seat_label || event.seat_id}</span>
                        <span className="text-xs text-muted-foreground">{format(new Date(event.ts), "HH:mm:ss")}</span>
                    </div>
                    <div className="text-sm whitespace-pre-wrap">{event.content}</div>
                    {event.stance && (
                        <div className="mt-2">
                            <Badge variant="secondary" className="text-xs">{event.stance}</Badge>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
