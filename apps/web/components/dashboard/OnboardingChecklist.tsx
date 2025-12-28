"use client"

import { useI18n } from "@/lib/i18n/client"
import { Check, Circle } from "lucide-react"

interface OnboardingChecklistProps {
    step1Complete: boolean
    step2Complete: boolean
    step3Complete: boolean
    onStep3Mark: () => void
}

export function OnboardingChecklist({
    step1Complete,
    step2Complete,
    step3Complete,
    onStep3Mark,
}: OnboardingChecklistProps) {
    const { t } = useI18n()

    const steps = [
        {
            number: 1,
            title: t("dashboard.onboarding.step1.title"),
            description: t("dashboard.onboarding.step1.description"),
            complete: step1Complete,
        },
        {
            number: 2,
            title: t("dashboard.onboarding.step2.title"),
            description: t("dashboard.onboarding.step2.description"),
            complete: step2Complete,
        },
        {
            number: 3,
            title: t("dashboard.onboarding.step3.title"),
            description: t("dashboard.onboarding.step3.description"),
            complete: step3Complete,
        },
    ]

    return (
        <div className="mb-8 rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50/30 p-6 shadow-sm dark:border-slate-700 dark:from-slate-800 dark:to-slate-900">
            {/* Header */}
            <div className="mb-6">
                <h2 className="mb-2 font-heading text-2xl font-bold text-slate-900 dark:text-white">
                    {t("dashboard.onboarding.checklist.title")}
                </h2>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                    {t("dashboard.onboarding.checklist.subtitle")}
                </p>
            </div>

            {/* Steps */}
            <div className="space-y-4">
                {steps.map((step) => (
                    <div
                        key={step.number}
                        className="flex items-start gap-4 rounded-lg bg-white/60 p-4 transition hover:bg-white dark:bg-slate-800/60 dark:hover:bg-slate-800"
                    >
                        {/* Status Icon */}
                        <div className="flex-shrink-0 pt-0.5">
                            {step.complete ? (
                                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500">
                                    <Check className="h-4 w-4 text-white" aria-hidden="true" />
                                    <span className="sr-only">Complete</span>
                                </div>
                            ) : (
                                <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-amber-400">
                                    <Circle className="h-3 w-3 text-amber-400" aria-hidden="true" />
                                    <span className="sr-only">Incomplete</span>
                                </div>
                            )}
                        </div>

                        {/* Content */}
                        <div className="flex-1">
                            <h3 className="mb-1 font-semibold text-slate-900 dark:text-white">
                                {step.number}. {step.title}
                            </h3>
                            <p className="text-sm text-slate-600 dark:text-slate-300">{step.description}</p>

                            {/* Step 3 Action Button */}
                            {step.number === 3 && !step.complete && step2Complete && (
                                <button
                                    onClick={onStep3Mark}
                                    className="mt-2 rounded-lg bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-900 transition hover:bg-amber-200 dark:bg-amber-900/50 dark:text-amber-200 dark:hover:bg-amber-900"
                                >
                                    {t("dashboard.onboarding.markReviewed")}
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
