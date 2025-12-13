"use client"

import { AlertCircle, X } from "lucide-react"
import { useState } from "react"

interface ErrorBannerProps {
    title?: string
    message: string
    type?: "error" | "warning" | "timeout"
    onDismiss?: () => void
    onRetry?: () => void
    dismissible?: boolean
}

export function ErrorBanner({
    title,
    message,
    type = "error",
    onDismiss,
    onRetry,
    dismissible = true,
}: ErrorBannerProps) {
    const [dismissed, setDismissed] = useState(false)

    const handleDismiss = () => {
        setDismissed(true)
        onDismiss?.()
    }

    if (dismissed) return null

    const styles = {
        error: {
            container: "border-red-200 bg-red-50",
            icon: "text-red-600",
            title: "text-red-900",
            text: "text-red-800",
        },
        warning: {
            container: "border-amber-200 bg-amber-50",
            icon: "text-amber-600",
            title: "text-amber-900",
            text: "text-amber-800",
        },
        timeout: {
            container: "border-orange-200 bg-orange-50",
            icon: "text-orange-600",
            title: "text-orange-900",
            text: "text-orange-800",
        },
    }

    const style = styles[type]

    return (
        <div
            className={`flex items-start gap-3 rounded-lg border p-4 ${style.container}`}
            role="alert"
            aria-live="polite"
        >
            {/* Icon */}
            <AlertCircle className={`h-5 w-5 flex-shrink-0 ${style.icon}`} aria-hidden="true" />

            {/* Content */}
            <div className="flex-1">
                {title && <h3 className={`mb-1 font-semibold ${style.title}`}>{title}</h3>}
                <p className={`text-sm ${style.text}`}>{message}</p>
                {onRetry && (
                    <button
                        onClick={onRetry}
                        className={`mt-2 text-sm font-semibold underline-offset-2 hover:underline ${style.title}`}
                    >
                        Try again
                    </button>
                )}
            </div>

            {/* Dismiss button */}
            {dismissible && (
                <button
                    onClick={handleDismiss}
                    className={`flex-shrink-0 rounded p-1 transition hover:bg-white/50 ${style.icon}`}
                    aria-label="Dismiss"
                >
                    <X className="h-4 w-4" />
                </button>
            )}
        </div>
    )
}
