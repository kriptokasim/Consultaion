/**
 * Patchset 76: VoteBar component
 * 
 * Voting control with up/down buttons, accessibility support, and keyboard navigation.
 */
"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "@/components/ui/button";

export type VoteValue = "up" | "down" | null;

interface VoteBarProps {
    /** Current vote value */
    value?: VoteValue;
    /** Called when vote changes */
    onVote?: (vote: VoteValue) => void;
    /** Whether voting is disabled */
    disabled?: boolean;
    /** Show labels next to icons */
    showLabels?: boolean;
    /** Additional class names */
    className?: string;
    /** Size variant */
    size?: "sm" | "md" | "lg";
    /** Aria label for the vote bar */
    "aria-label"?: string;
}

export function VoteBar({
    value,
    onVote,
    disabled = false,
    showLabels = false,
    className,
    size = "md",
    "aria-label": ariaLabel = "Vote on this response",
}: VoteBarProps) {
    const [localValue, setLocalValue] = useState<VoteValue>(value ?? null);

    const handleVote = useCallback(
        (vote: VoteValue) => {
            if (disabled) return;

            // Toggle off if same vote clicked
            const newValue = localValue === vote ? null : vote;
            setLocalValue(newValue);
            onVote?.(newValue);
        },
        [disabled, localValue, onVote]
    );

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent, vote: VoteValue) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleVote(vote);
            }
        },
        [handleVote]
    );

    const sizeClasses = {
        sm: "h-7 w-7",
        md: "h-9 w-9",
        lg: "h-11 w-11",
    };

    const iconSizes = {
        sm: "h-3.5 w-3.5",
        md: "h-4 w-4",
        lg: "h-5 w-5",
    };

    return (
        <div
            className={cn("flex items-center gap-2", className)}
            role="group"
            aria-label={ariaLabel}
        >
            <Button
                variant={localValue === "up" ? "default" : "outline"}
                size="icon"
                className={cn(
                    sizeClasses[size],
                    "rounded-full transition-all",
                    localValue === "up"
                        ? "bg-emerald-500 hover:bg-emerald-600 text-white border-emerald-500"
                        : "hover:border-emerald-300 hover:text-emerald-600"
                )}
                onClick={() => handleVote("up")}
                onKeyDown={(e) => handleKeyDown(e, "up")}
                disabled={disabled}
                aria-label="Vote up"
                aria-pressed={localValue === "up"}
            >
                <ThumbsUp className={iconSizes[size]} aria-hidden="true" />
            </Button>

            {showLabels && (
                <span className="text-xs text-slate-500">Helpful</span>
            )}

            <Button
                variant={localValue === "down" ? "default" : "outline"}
                size="icon"
                className={cn(
                    sizeClasses[size],
                    "rounded-full transition-all",
                    localValue === "down"
                        ? "bg-rose-500 hover:bg-rose-600 text-white border-rose-500"
                        : "hover:border-rose-300 hover:text-rose-600"
                )}
                onClick={() => handleVote("down")}
                onKeyDown={(e) => handleKeyDown(e, "down")}
                disabled={disabled}
                aria-label="Vote down"
                aria-pressed={localValue === "down"}
            >
                <ThumbsDown className={iconSizes[size]} aria-hidden="true" />
            </Button>

            {showLabels && (
                <span className="text-xs text-slate-500">Not helpful</span>
            )}
        </div>
    );
}

export default VoteBar;
