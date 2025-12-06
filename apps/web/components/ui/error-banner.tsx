import { AlertCircle, Info, RefreshCw, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface ErrorBannerProps {
    title?: string
    message: string
    variant?: "error" | "warning" | "info"
    retryAction?: () => void
    onDismiss?: () => void
    className?: string
}

export function ErrorBanner({
    title,
    message,
    variant = "error",
    retryAction,
    onDismiss,
    className,
}: ErrorBannerProps) {
    const styles = {
        error: "bg-red-50 border-red-200 text-red-900 dark:bg-red-900/20 dark:border-red-900/50 dark:text-red-200",
        warning: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-900/20 dark:border-amber-900/50 dark:text-amber-200",
        info: "bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-900/20 dark:border-blue-900/50 dark:text-blue-200",
    }

    const icons = {
        error: AlertCircle,
        warning: AlertCircle,
        info: Info,
    }

    const Icon = icons[variant]

    return (
        <div
            className={cn(
                "flex items-start gap-4 rounded-lg border p-4 shadow-sm transition-all animate-in fade-in slide-in-from-top-2",
                styles[variant],
                className
            )}
            role="alert"
        >
            <Icon className="mt-0.5 h-5 w-5 shrink-0 opacity-80" />
            <div className="flex-1 space-y-1">
                {title && <h5 className="font-medium leading-none tracking-tight">{title}</h5>}
                <div className="text-sm opacity-90">{message}</div>
                {retryAction && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={retryAction}
                        className="mt-2 h-8 gap-2 border-current bg-transparent px-3 text-xs font-medium opacity-80 hover:bg-white/20 hover:opacity-100"
                    >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Retry
                    </Button>
                )}
            </div>
            {onDismiss && (
                <button
                    onClick={onDismiss}
                    className="rounded-full p-1 opacity-60 hover:bg-black/5 hover:opacity-100 dark:hover:bg-white/10"
                    aria-label="Dismiss"
                >
                    <XCircle className="h-5 w-5" />
                </button>
            )}
        </div>
    )
}
