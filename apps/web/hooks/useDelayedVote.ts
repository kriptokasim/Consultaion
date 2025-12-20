/**
 * Patchset 76: useDelayedVote hook
 * 
 * Tracks user engagement (scroll and dwell time) before showing vote CTA.
 * This ensures votes are more deliberate and higher-signal.
 */
import { useState, useEffect, useCallback, useRef } from 'react';

interface UseDelayedVoteOptions {
    /** Minimum dwell time in milliseconds before vote can show */
    dwellTimeMs?: number;
    /** Whether to track scroll position */
    trackScroll?: boolean;
    /** Scroll threshold as percentage (0-1) */
    scrollThreshold?: number;
    /** Whether feature is enabled */
    enabled?: boolean;
}

interface UseDelayedVoteReturn {
    /** Whether vote CTA can be shown */
    canShowVote: boolean;
    /** Current dwell time in ms */
    dwellTime: number;
    /** Whether user has scrolled past threshold */
    hasScrolledPast: boolean;
    /** Manually trigger vote visibility */
    forceShow: () => void;
    /** Reset the state */
    reset: () => void;
}

export function useDelayedVote(
    options: UseDelayedVoteOptions = {}
): UseDelayedVoteReturn {
    const {
        dwellTimeMs = 5000, // 5 seconds default
        trackScroll = true,
        scrollThreshold = 0.8, // 80% scroll
        enabled = true,
    } = options;

    const [dwellTime, setDwellTime] = useState(0);
    const [hasScrolledPast, setHasScrolledPast] = useState(false);
    const [forcedShow, setForcedShow] = useState(false);
    const startTimeRef = useRef<number>(Date.now());
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    // Track dwell time
    useEffect(() => {
        if (!enabled) return;

        startTimeRef.current = Date.now();

        intervalRef.current = setInterval(() => {
            setDwellTime(Date.now() - startTimeRef.current);
        }, 500);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [enabled]);

    // Track scroll position
    useEffect(() => {
        if (!enabled || !trackScroll) return;

        const handleScroll = () => {
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrolled = window.scrollY / scrollHeight;

            if (scrolled >= scrollThreshold) {
                setHasScrolledPast(true);
            }
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
        return () => window.removeEventListener('scroll', handleScroll);
    }, [enabled, trackScroll, scrollThreshold]);

    const forceShow = useCallback(() => {
        setForcedShow(true);
    }, []);

    const reset = useCallback(() => {
        setDwellTime(0);
        setHasScrolledPast(false);
        setForcedShow(false);
        startTimeRef.current = Date.now();
    }, []);

    const canShowVote = !enabled || forcedShow || dwellTime >= dwellTimeMs || hasScrolledPast;

    return {
        canShowVote,
        dwellTime,
        hasScrolledPast,
        forceShow,
        reset,
    };
}

export default useDelayedVote;
