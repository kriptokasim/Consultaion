"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_ORIGIN } from "@/lib/config/runtime";

interface ProviderStatus {
    provider: string;
    status: "healthy" | "degraded" | "down";
    latency?: number;
    errorRate?: number;
}

interface ProviderHealthBannerProps {
    className?: string;
    dismissible?: boolean;
    checkInterval?: number; // ms, default 60000
}

/**
 * Displays a banner when AI providers are degraded or down.
 * Fetches status from /api/health/providers endpoint.
 */
export function ProviderHealthBanner({
    className,
    dismissible = true,
    checkInterval = 60000,
}: ProviderHealthBannerProps) {
    const [providers, setProviders] = useState<ProviderStatus[]>([]);
    const [dismissed, setDismissed] = useState(false);
    const [loading, setLoading] = useState(true);

    const fetchHealth = async () => {
        try {
            const apiBase = API_ORIGIN;
            const response = await fetch(`${apiBase}/api/health/providers`, {
                credentials: "include",
            });

            if (!response.ok) {
                // Endpoint might not exist yet
                setProviders([]);
                return;
            }

            const data = await response.json();
            setProviders(data.providers || []);
        } catch {
            // Silently fail - endpoint might not exist
            setProviders([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, checkInterval);
        return () => clearInterval(interval);
    }, [checkInterval]);

    // Filter for unhealthy providers
    const unhealthy = providers.filter((p) => p.status !== "healthy");

    // Don't show if dismissed, loading, or all healthy
    if (dismissed || loading || unhealthy.length === 0) {
        return null;
    }

    const hasDown = unhealthy.some((p) => p.status === "down");
    const severity = hasDown ? "error" : "warning";

    return (
        <div
            className={cn(
                "relative rounded-xl border px-4 py-3 text-sm",
                severity === "error"
                    ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200"
                    : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200",
                className
            )}
            role="alert"
        >
            <div className="flex items-start gap-3">
                <AlertTriangle
                    className={cn(
                        "h-5 w-5 shrink-0",
                        severity === "error" ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400"
                    )}
                />
                <div className="flex-1">
                    <p className="font-semibold">
                        {hasDown ? "AI Provider Unavailable" : "AI Provider Degraded"}
                    </p>
                    <p className="mt-1 text-sm opacity-90">
                        {unhealthy.map((p) => p.provider).join(", ")}{" "}
                        {unhealthy.length === 1 ? "is" : "are"} experiencing issues.
                        {!hasDown && " Response times may be slower than usual."}
                    </p>
                    <div className="mt-2 flex items-center gap-3">
                        <button
                            onClick={() => fetchHealth()}
                            className="inline-flex items-center gap-1 text-xs font-semibold underline-offset-2 hover:underline"
                        >
                            <RefreshCw className="h-3 w-3" />
                            Refresh status
                        </button>
                        <span className="text-xs opacity-70">
                            Try another model or retry later
                        </span>
                    </div>
                </div>
                {dismissible && (
                    <button
                        onClick={() => setDismissed(true)}
                        className="shrink-0 rounded-full p-1 hover:bg-black/10 dark:hover:bg-white/10"
                        aria-label="Dismiss"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}
            </div>
        </div>
    );
}

/**
 * Hook to check provider health status
 */
export function useProviderHealth() {
    const [status, setStatus] = useState<{
        loading: boolean;
        healthy: boolean;
        providers: ProviderStatus[];
    }>({
        loading: true,
        healthy: true,
        providers: [],
    });

    useEffect(() => {
        const check = async () => {
            try {
                const apiBase = API_ORIGIN;
                const response = await fetch(`${apiBase}/api/health/providers`, {
                    credentials: "include",
                });

                if (!response.ok) {
                    setStatus({ loading: false, healthy: true, providers: [] });
                    return;
                }

                const data = await response.json();
                const providers = data.providers || [];
                const healthy = providers.every((p: ProviderStatus) => p.status === "healthy");

                setStatus({ loading: false, healthy, providers });
            } catch {
                setStatus({ loading: false, healthy: true, providers: [] });
            }
        };

        check();
    }, []);

    return status;
}
