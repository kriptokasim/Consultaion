"use client";

import React from "react";
import { AlertCircle, RefreshCcw } from "lucide-react";

interface SectionErrorBoundaryProps {
    children: React.ReactNode;
    /** Title shown when this section crashes */
    title?: string;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

/**
 * Granular error boundary for individual sections of a page.
 * When a section crashes, only that section shows a fallback,
 * keeping the rest of the page functional.
 */
export class SectionErrorBoundary extends React.Component<SectionErrorBoundaryProps, State> {
    constructor(props: SectionErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: React.ErrorInfo) {
        console.error(`[SectionErrorBoundary] ${this.props.title || "Section"} crashed:`, error, info);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="rounded-2xl border border-rose-200 bg-rose-50/70 p-6 text-center dark:border-rose-800 dark:bg-rose-950/30">
                    <AlertCircle className="mx-auto h-8 w-8 text-rose-500" />
                    <h3 className="mt-3 text-sm font-semibold text-rose-800 dark:text-rose-300">
                        {this.props.title || "Section"} failed to load
                    </h3>
                    <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">
                        {this.state.error?.message || "An unexpected error occurred."}
                    </p>
                    <button
                        type="button"
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-50 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-300 dark:hover:bg-rose-900"
                    >
                        <RefreshCcw className="h-3 w-3" />
                        Retry
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
