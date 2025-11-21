import { cn } from "@/lib/utils"
import { X, Check, AlertCircle, Info } from "lucide-react"

interface ToastProps {
  id: string
  title?: string
  description: string
  type?: "default" | "success" | "error" | "info"
  duration?: number
  onClose: (id: string) => void
}

export function ModernToast({
  id,
  title,
  description,
  type = "default",
  onClose,
}: ToastProps) {
  const icons = {
    default: null,
    success: <Check className="h-5 w-5 text-success" />,
    error: <AlertCircle className="h-5 w-5 text-destructive" />,
    info: <Info className="h-5 w-5 text-info" />,
  }

  const colors = {
    default: "border-border bg-card",
    success: "border-success/30 bg-success-light dark:bg-success-dark/20",
    error: "border-destructive/30 bg-destructive/10",
    info: "border-info/30 bg-info-light dark:bg-info-dark/20",
  }

  return (
    <div
      className={cn(
        "animate-slide-in-up flex items-start gap-3 rounded-lg border px-4 py-3 shadow-smooth-lg backdrop-blur-xs transition-all duration-300",
        colors[type],
      )}
      role="alert"
    >
      {icons[type] && <div className="mt-0.5 flex-shrink-0">{icons[type]}</div>}
      <div className="flex-1">
        {title && <p className="font-semibold text-foreground">{title}</p>}
        <p className={cn("text-sm text-foreground/80", title && "mt-1")}>
          {description}
        </p>
      </div>
      <button
        onClick={() => onClose(id)}
        className="mt-0.5 flex-shrink-0 text-foreground/50 transition-colors hover:text-foreground"
        aria-label="Close notification"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
