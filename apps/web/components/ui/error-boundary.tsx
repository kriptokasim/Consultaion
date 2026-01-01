"use client";

import { Component, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
    children: ReactNode;
    fallback?: ReactNode;
    onReset?: () => void;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        // Log to error reporting service (e.g., Sentry)
        console.error("ErrorBoundary caught an error:", error, errorInfo);

        // You can send to Sentry here if configured
        // Sentry.captureException(error, { extra: errorInfo });
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
        this.props.onReset?.();
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-red-200 bg-red-50/50 p-8 text-center dark:border-red-900/50 dark:bg-red-950/20">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400">
                        <AlertTriangle className="h-7 w-7" />
                    </div>
                    <h2 className="mt-4 text-lg font-semibold text-slate-900 dark:text-white">
                        Something went wrong
                    </h2>
                    <p className="mt-2 max-w-md text-sm text-slate-600 dark:text-slate-300">
                        We encountered an unexpected error. Please try again or contact support if the problem persists.
                    </p>
                    {this.state.error && (
                        <details className="mt-4 max-w-md text-left">
                            <summary className="cursor-pointer text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                                Technical details
                            </summary>
                            <pre className="mt-2 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                {this.state.error.message}
                            </pre>
                        </details>
                    )}
                    <Button
                        onClick={this.handleReset}
                        className="mt-6"
                        variant="outline"
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Try again
                    </Button>
                </div>
            );
        }

        return this.props.children;
    }
}

// Functional wrapper for easier use with hooks
export function withErrorBoundary<P extends object>(
    WrappedComponent: React.ComponentType<P>,
    fallback?: ReactNode
) {
    return function WithErrorBoundary(props: P) {
        return (
            <ErrorBoundary fallback={fallback}>
                <WrappedComponent {...props} />
            </ErrorBoundary>
        );
    };
}
