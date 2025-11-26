'use client'

interface DebateProgressBarProps {
    active: boolean
}

/**
 * DebateProgressBar - Subtle top progress indicator
 * 
 * Shows an animated progress bar at the top of the viewport when a debate is running.
 */
export function DebateProgressBar({ active }: DebateProgressBarProps) {
    if (!active) return null

    return (
        <div className="fixed left-0 right-0 top-0 z-30">
            <div className="mx-auto max-w-4xl px-4">
                <div className="h-0.5 overflow-hidden rounded-full bg-brand-border/60">
                    <div className="h-full w-1/3 animate-pulse bg-brand-accent" />
                </div>
            </div>
        </div>
    )
}
