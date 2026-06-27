"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp, Loader2, Wifi, WifiOff, Save, Copy } from "lucide-react";
import Image from "next/image";

import { sanitizeMarkdown } from "@/lib/sanitize";
import type { ModelState } from "@/lib/streaming/types";

/* ─── provider accent colours ─── */
const PROVIDER_COLORS: Record<string, { bg: string; border: string; text: string; accent: string; glow: string }> = {
    openai: {
        bg: "bg-emerald-50 dark:bg-emerald-950/30",
        border: "border-emerald-200 dark:border-emerald-800",
        text: "text-emerald-700 dark:text-emerald-300",
        accent: "bg-emerald-100 dark:bg-emerald-900/50",
        glow: "shadow-emerald-100/50 dark:shadow-emerald-900/30",
    },
    anthropic: {
        bg: "bg-orange-50 dark:bg-orange-950/30",
        border: "border-orange-200 dark:border-orange-800",
        text: "text-orange-700 dark:text-orange-300",
        accent: "bg-orange-100 dark:bg-orange-900/50",
        glow: "shadow-orange-100/50 dark:shadow-orange-900/30",
    },
    gemini: {
        bg: "bg-blue-50 dark:bg-blue-950/30",
        border: "border-blue-200 dark:border-blue-800",
        text: "text-blue-700 dark:text-blue-300",
        accent: "bg-blue-100 dark:bg-blue-900/50",
        glow: "shadow-blue-100/50 dark:shadow-blue-900/30",
    },
    openrouter: {
        bg: "bg-violet-50 dark:bg-violet-950/30",
        border: "border-violet-200 dark:border-violet-800",
        text: "text-violet-700 dark:text-violet-300",
        accent: "bg-violet-100 dark:bg-violet-900/50",
        glow: "shadow-violet-100/50 dark:shadow-violet-900/30",
    },
};

const DEFAULT_COLORS = {
    bg: "bg-slate-50 dark:bg-slate-900/30",
    border: "border-slate-200 dark:border-slate-700",
    text: "text-slate-700 dark:text-slate-300",
    accent: "bg-slate-100 dark:bg-slate-800",
    glow: "shadow-slate-100/50 dark:shadow-slate-800/30",
};

export function getColors(provider?: string) {
    return PROVIDER_COLORS[provider || ""] || DEFAULT_COLORS;
}

/* ─── Extract a human-readable error from raw content ─── */
export function extractFriendlyError(raw: string): { friendly: string; technical: string | null } {
    if (!raw) return { friendly: "This model did not return a response.", technical: null };

    const lower = raw.toLowerCase();

    if (lower.includes("credit balance is too low") || lower.includes("insufficient") || lower.includes("requires more credits"))
        return { friendly: "This provider's API credits have been exhausted. The account needs to be topped up.", technical: raw };

    if (lower.includes("api key not valid") || lower.includes("invalid api key") || lower.includes("authentication"))
        return { friendly: "The API key for this provider is invalid or expired.", technical: raw };

    if (lower.includes("rate limit") || lower.includes("429") || lower.includes("too many requests"))
        return { friendly: "This provider is temporarily rate-limited. Please try again in a moment.", technical: raw };

    if (lower.includes("timeout") || lower.includes("timed out"))
        return { friendly: "This model took too long to respond and was timed out.", technical: raw };

    if (lower.includes("error") || lower.includes("exception") || lower.includes("traceback") || lower.includes("failed"))
        return { friendly: "This model encountered an error while processing your request.", technical: raw };

    // Content looks normal — not an error
    return { friendly: "", technical: null };
}

/* ─── Model response type ─── */
export interface ModelResponse {
    model_id: string;
    display_name: string;
    provider: string;
    content: string;
    logo_url?: string;
    persona_type?: string;
    success: boolean;
}

/* ─── Logo component with fallback ─── */
export function ModelLogo({ logoUrl, displayName, size = 28 }: { logoUrl?: string; displayName: string; size?: number }) {
    if (logoUrl) {
        return (
            <Image
                src={logoUrl}
                alt={displayName}
                width={size}
                height={size}
                className="rounded-md"
                unoptimized
            />
        );
    }
    return (
        <div
            className="flex items-center justify-center rounded-md bg-primary/10 text-primary font-bold"
            style={{ width: size, height: size, fontSize: size * 0.45 }}
        >
            {displayName.charAt(0)}
        </div>
    );
}

/* ─── Skeleton card while loading ─── */
export function SkeletonCard({ index, className = "" }: { index: number; className?: string }) {
    const delays = ["", "animation-delay-150", "animation-delay-300", "animation-delay-500"];
    return (
        <div className={`flex flex-col rounded-2xl border border-border bg-card shadow-sm overflow-hidden opacity-60 min-h-[350px] sm:min-h-[400px] ${delays[index] || ""} ${className}`}>
            <div className="p-4 border-b border-border flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-muted animate-pulse" />
                <div className="flex-1 space-y-1.5">
                    <div className="h-4 w-28 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-20 bg-muted animate-pulse rounded" />
                </div>
            </div>
            <div className="p-5 space-y-2 flex-1">
                <div className="h-4 w-full bg-muted animate-pulse rounded" />
                <div className="h-4 w-5/6 bg-muted animate-pulse rounded" />
                <div className="h-4 w-4/6 bg-muted animate-pulse rounded" />
                <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
                <div className="h-4 w-2/3 bg-muted animate-pulse rounded" />
            </div>
        </div>
    );
}

/* ─── Friendly error card body ─── */
export function ErrorCardBody({
    friendly,
    technical,
    displayName,
    onRetry,
}: {
    friendly: string;
    technical: string | null;
    displayName: string;
    onRetry?: () => Promise<void>;
}) {
    const [showDetails, setShowDetails] = useState(false);
    const [retrying, setRetrying] = useState(false);
    const [retryError, setRetryError] = useState<string | null>(null);

    const handleRetryClick = async () => {
        if (!onRetry) return;
        setRetrying(true);
        setRetryError(null);
        try {
            await onRetry();
        } catch (err: any) {
            setRetryError(err.message || "Retry failed");
        } finally {
            setRetrying(false);
        }
    };

    return (
        <div className="p-5 flex-1 flex flex-col items-center justify-center text-center gap-3">
            <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-3">
                <AlertTriangle className="h-6 w-6 text-red-500 dark:text-red-400" />
            </div>
            <div>
                <p className="text-sm font-medium text-foreground">{displayName} Unavailable</p>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed max-w-[240px] mx-auto">
                    {friendly}
                </p>
            </div>
            {technical && (
                <button
                    type="button"
                    onClick={() => setShowDetails(!showDetails)}
                    aria-expanded={showDetails}
                    aria-label={`${showDetails ? "Hide" : "Show"} error details for ${displayName}`}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground/70 hover:text-muted-foreground transition-colors"
                >
                    {showDetails ? "Hide" : "Show"} details
                    {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
            )}
            {showDetails && technical && (
                <pre className="mt-1 w-full max-h-32 overflow-auto rounded-lg bg-muted/50 p-2 text-[10px] text-muted-foreground text-left whitespace-pre-wrap break-all">
                    {technical.slice(0, 500)}{technical.length > 500 ? "…" : ""}
                </pre>
            )}
            {onRetry ? (
                <div className="mt-3 flex flex-col items-center gap-1.5 w-full">
                    <button
                        onClick={handleRetryClick}
                        disabled={retrying}
                        className="inline-flex items-center justify-center px-4 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs shadow hover:bg-primary/95 transition-all disabled:opacity-50"
                    >
                        {retrying ? (
                            <>
                                <span className="h-3 w-3 mr-1.5 rounded-full border-2 border-primary-foreground border-t-transparent animate-spin animate-spin" />
                                Retrying...
                            </>
                        ) : (
                            "Retry Agent"
                        )}
                    </button>
                    {retryError && (
                        <span className="text-[10px] text-red-500 font-medium">{retryError}</span>
                    )}
                </div>
            ) : (
                <span className="mt-3 inline-flex items-center justify-center rounded-full bg-muted px-3 py-1.5 text-[11px] font-medium text-muted-foreground/80 border border-border">
                    Retry unavailable
                </span>
            )}
        </div>
    );
}

/* ─── Streaming state badge ─── */
function StreamingStateBadge({ state }: { state: ModelState }) {
    switch (state) {
        case "queued":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:text-slate-400">
                    <Loader2 className="h-2.5 w-2.5 animate-spin" /> Queued
                </span>
            );
        case "connecting":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                    <Wifi className="h-2.5 w-2.5 animate-pulse" /> Connecting
                </span>
            );
        case "streaming":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:text-blue-300">
                    <Loader2 className="h-2.5 w-2.5 animate-spin" /> Streaming
                </span>
            );
        case "persisting":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 dark:bg-purple-900/30 px-2 py-0.5 text-[10px] font-medium text-purple-700 dark:text-purple-300">
                    <Save className="h-2.5 w-2.5" /> Saving
                </span>
            );
        case "failed":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-red-100 dark:bg-red-900/30 px-2 py-0.5 text-[10px] font-medium text-red-600 dark:text-red-400">
                    <WifiOff className="h-2.5 w-2.5" /> Failed
                </span>
            );
        default:
            return null;
    }
}

/* ─── Model response card ─── */
interface ModelCardProps {
    resp: ModelResponse;
    className?: string;
    onRetry?: (personaName: string) => Promise<void>;
}

export function ModelCard({ resp, className = "", onRetry }: ModelCardProps) {
    const colors = getColors(resp.provider);
    const errorInfo = !resp.success ? extractFriendlyError(resp.content) : null;
    const isError = !resp.success && errorInfo;
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (resp.content) {
            navigator.clipboard.writeText(resp.content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }, [resp.content]);

    return (
        <article
            className={`flex flex-col rounded-2xl border ${colors.border} ${colors.bg} shadow-sm hover:shadow-md ${colors.glow} transition-all duration-200 overflow-hidden min-h-[350px] sm:min-h-[400px] ${className}`}
            aria-label={`Response from ${resp.display_name}`}
        >
            {/* Card Header */}
            <div className={`p-4 border-b ${colors.border} flex items-center gap-3`}>
                <div className={`shrink-0 rounded-xl ${colors.accent} p-2`}>
                    <ModelLogo
                        logoUrl={resp.logo_url}
                        displayName={resp.display_name}
                    />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <p className={`font-semibold text-sm truncate ${colors.text}`}>
                            {resp.display_name}
                        </p>
                        {resp.success ? (
                            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                        ) : (
                            <XCircle className="h-3.5 w-3.5 shrink-0 text-red-500" />
                        )}
                    </div>
                </div>
                {resp.success && resp.content && (
                    <button 
                        onClick={handleCopy} 
                        className="shrink-0 p-1.5 hover:bg-black/5 dark:hover:bg-white/10 rounded-md transition-colors group"
                        aria-label="Copy response"
                        title="Copy response text"
                    >
                        {copied ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                            <Copy className="h-3.5 w-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
                        )}
                    </button>
                )}
            </div>

            {/* Card Body */}
            {isError ? (
                <ErrorCardBody
                    friendly={errorInfo.friendly}
                    technical={errorInfo.technical}
                    displayName={resp.display_name}
                    onRetry={onRetry ? () => onRetry(resp.display_name) : undefined}
                />
            ) : (
                <div className="p-5 flex-1 overflow-y-auto max-h-[400px] prose prose-sm dark:prose-invert max-w-none custom-scrollbar">
                    {resp.content ? (
                        <div
                            className="text-sm leading-relaxed text-foreground/90"
                            dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(resp.content) }}
                        />
                    ) : (
                        <span className="italic text-muted-foreground">No response received.</span>
                    )}
                </div>
            )}
        </article>
    );
}

/* ─── Streaming model card (FH103) ─── */
interface StreamingModelCardProps {
    displayName: string;
    provider?: string;
    logoUrl?: string;
    state: ModelState;
    accumulatedText: string;
    errorCode?: string;
    errorMessage?: string;
    className?: string;
    onRetry?: (displayName: string) => Promise<void>;
}

const BUFFER_FLUSH_INTERVAL_MS = 40;

export function StreamingModelCard({
    displayName,
    provider,
    logoUrl,
    state,
    accumulatedText,
    errorCode,
    errorMessage,
    className = "",
    onRetry,
}: StreamingModelCardProps) {
    const colors = getColors(provider);
    const bodyRef = useRef<HTMLDivElement>(null);
    const [displayedText, setDisplayedText] = useState("");
    const [copied, setCopied] = useState(false);
    const lastFlushRef = useRef(0);
    const animFrameRef = useRef<number>(0);

    const handleCopy = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (accumulatedText) {
            navigator.clipboard.writeText(accumulatedText);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }, [accumulatedText]);

    // Buffered rendering: flush every BUFFER_FLUSH_INTERVAL_MS
    useEffect(() => {
        const now = Date.now();
        if (now - lastFlushRef.current >= BUFFER_FLUSH_INTERVAL_MS || state === "completed" || state === "failed") {
            setDisplayedText(accumulatedText);
            lastFlushRef.current = now;
        } else {
            animFrameRef.current = requestAnimationFrame(() => {
                setDisplayedText(accumulatedText);
                lastFlushRef.current = Date.now();
            });
        }
        return () => cancelAnimationFrame(animFrameRef.current);
    }, [accumulatedText, state]);

    // Auto-scroll only when near bottom
    useEffect(() => {
        const el = bodyRef.current;
        if (!el) return;
        const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        if (nearBottom) {
            el.scrollTop = el.scrollHeight;
        }
    }, [displayedText]);

    const isTerminal = state === "completed" || state === "failed";
    const isError = state === "failed";

    return (
        <article
            className={`flex flex-col rounded-2xl border ${colors.border} ${colors.bg} shadow-sm hover:shadow-md ${colors.glow} transition-all duration-200 overflow-hidden min-h-[350px] sm:min-h-[400px] ${className}`}
            aria-label={`Response from ${displayName}`}
            aria-live="polite"
            aria-atomic="false"
        >
            {/* Card Header */}
            <div className={`p-4 border-b ${colors.border} flex items-center gap-3`}>
                <div className={`shrink-0 rounded-xl ${colors.accent} p-2`}>
                    <ModelLogo logoUrl={logoUrl} displayName={displayName} />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <p className={`font-semibold text-sm truncate ${colors.text}`}>
                            {displayName}
                        </p>
                        <StreamingStateBadge state={state} />
                    </div>
                </div>
                {(state === "completed" || state === "streaming") && accumulatedText && (
                    <button 
                        onClick={handleCopy} 
                        className="shrink-0 p-1.5 hover:bg-black/5 dark:hover:bg-white/10 rounded-md transition-colors group"
                        aria-label="Copy response"
                        title="Copy response text"
                    >
                        {copied ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                            <Copy className="h-3.5 w-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
                        )}
                    </button>
                )}
            </div>

            {/* Card Body */}
            {isError ? (
                <ErrorCardBody
                    friendly={errorMessage || "This model failed to respond."}
                    technical={errorCode || null}
                    displayName={displayName}
                    onRetry={onRetry ? () => onRetry(displayName) : undefined}
                />
            ) : (
                <div
                    ref={bodyRef}
                    className="p-5 flex-1 overflow-y-auto max-h-[400px] prose prose-sm dark:prose-invert max-w-none custom-scrollbar"
                >
                    {displayedText ? (
                        isTerminal ? (
                            // Rendered markdown after completion
                            <div
                                className="text-sm leading-relaxed text-foreground/90"
                                dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(displayedText) }}
                            />
                        ) : (
                            // Plain text during streaming
                            <pre className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap font-sans">
                                {displayedText}
                                <span className="inline-block h-4 w-0.5 bg-foreground/40 animate-pulse ml-0.5 align-middle" />
                            </pre>
                        )
                    ) : state === "queued" || state === "connecting" ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>Waiting for model...</span>
                        </div>
                    ) : (
                        <span className="italic text-muted-foreground">No response received.</span>
                    )}
                </div>
            )}
        </article>
    );
}
