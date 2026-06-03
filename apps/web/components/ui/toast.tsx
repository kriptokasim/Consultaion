"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Check, AlertCircle, X, Info } from "lucide-react";

type ToastVariant = "default" | "success" | "error" | "info";

type Toast = {
  id: number;
  title: string;
  description?: string;
  variant?: ToastVariant;
};

type ToastContextValue = {
  pushToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: number) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const value = useMemo(() => ({ pushToast, removeToast }), [pushToast, removeToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

function ToastViewport({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: number) => void }) {
  const icons = {
    default: <Info className="h-5 w-5 text-slate-500 dark:text-slate-400" />,
    info: <Info className="h-5 w-5 text-blue-500 dark:text-blue-400" />,
    success: <Check className="h-5 w-5 text-emerald-500 dark:text-emerald-400" />,
    error: <AlertCircle className="h-5 w-5 text-red-500 dark:text-red-400" />,
  };

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-3 px-4">
      {toasts.map((toast) => {
        const variant = toast.variant || "default";
        return (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto animate-slide-in-up flex w-full max-w-md items-start gap-3 rounded-2xl border p-4 text-sm shadow-xl backdrop-blur-md transition-all duration-300",
              variant === "success" && "border-emerald-100 bg-emerald-50/95 text-emerald-950 dark:border-emerald-900/50 dark:bg-emerald-950/90 dark:text-emerald-50",
              variant === "error" && "border-red-100 bg-red-50/95 text-red-950 dark:border-red-900/50 dark:bg-red-950/90 dark:text-red-50",
              variant === "info" && "border-blue-100 bg-blue-50/95 text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/90 dark:text-blue-50",
              variant === "default" && "border-slate-200 bg-white/95 text-slate-900 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-50",
            )}
            role="alert"
          >
            <div className="mt-0.5 flex-shrink-0">{icons[variant]}</div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold leading-none">{toast.title}</p>
              {toast.description && (
                <p className="mt-1 text-xs opacity-90 leading-normal">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => onRemove(toast.id)}
              className="mt-0.5 flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              aria-label="Close notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
