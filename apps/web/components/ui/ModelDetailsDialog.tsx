"use client"

import { X, CheckCircle2, AlertCircle, Target } from "lucide-react"
import { useEffect } from "react"
import { useI18n } from "@/lib/i18n/client"
import type { ModelDetail } from "@/lib/modelDetails"

interface ModelDetailsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    model: ModelDetail | null
}

export function ModelDetailsDialog({ open, onOpenChange, model }: ModelDetailsDialogProps) {
    const { t } = useI18n()

    // Handle ESC key
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === "Escape" && open) {
                onOpenChange(false)
            }
        }
        window.addEventListener("keydown", handleEsc)
        return () => window.removeEventListener("keydown", handleEsc)
    }, [open, onOpenChange])

    // Prevent body scroll when modal is open
    useEffect(() => {
        if (open) {
            document.body.style.overflow = "hidden"
        } else {
            document.body.style.overflow = ""
        }
        return () => {
            document.body.style.overflow = ""
        }
    }, [open])

    if (!open || !model) return null

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
                onClick={() => onOpenChange(false)}
                aria-hidden="true"
            />

            {/* Modal */}
            <div
                className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl border border-amber-200/70 bg-gradient-to-br from-white to-amber-50/30 p-8 shadow-2xl"
                role="dialog"
                aria-modal="true"
                aria-labelledby="model-dialog-title"
            >
                {/* Header */}
                <div className="mb-6 flex items-start justify-between">
                    <div>
                        <h2 id="model-dialog-title" className="text-3xl font-display font-bold text-[#3a2a1a]">
                            {model.name}
                        </h2>
                        <p className="mt-1 text-sm text-amber-700">{model.provider}</p>
                    </div>
                    <button
                        onClick={() => onOpenChange(false)}
                        className="rounded-lg p-2 text-amber-900/70 transition hover:bg-amber-100 hover:text-amber-900"
                        aria-label={t("models.details.close")}
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Strengths */}
                <section className="mb-6">
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-green-800">
                        <CheckCircle2 className="h-5 w-5" />
                        {t("models.details.strengths")}
                    </h3>
                    <ul className="space-y-2">
                        {model.strengths.map((strength, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[#5a4a3a]">
                                <span className="mt-1 text-green-600">✓</span>
                                <span>{strength}</span>
                            </li>
                        ))}
                    </ul>
                </section>

                {/* Limitations */}
                <section className="mb-6">
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-800">
                        <AlertCircle className="h-5 w-5" />
                        {t("models.details.limitations")}
                    </h3>
                    <ul className="space-y-2">
                        {model.limitations.map((limitation, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[#5a4a3a]">
                                <span className="mt-1 text-amber-600">⚠</span>
                                <span>{limitation}</span>
                            </li>
                        ))}
                    </ul>
                </section>

                {/* Best For */}
                <section className="rounded-xl border border-amber-200/70 bg-amber-50/50 p-5">
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-900">
                        <Target className="h-5 w-5" />
                        {t("models.details.bestFor")}
                    </h3>
                    <ul className="space-y-2">
                        {model.bestFor.map((use, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[#5a4a3a]">
                                <span className="mt-1 text-amber-600">🎯</span>
                                <span>{use}</span>
                            </li>
                        ))}
                    </ul>
                </section>

                {/* Footer */}
                <div className="mt-6 text-center">
                    <button
                        onClick={() => onOpenChange(false)}
                        className="rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-6 py-2 font-semibold text-white shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
                    >
                        {t("models.details.close")}
                    </button>
                </div>
            </div>
        </>
    )
}
