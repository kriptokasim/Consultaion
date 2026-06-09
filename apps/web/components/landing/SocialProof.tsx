"use client"

import { useI18n } from "@/lib/i18n/client"
import { ShieldCheck, GitCompare, Lightbulb, FileText } from "lucide-react"

const useCases = [
    {
        icon: ShieldCheck,
        titleKey: "landing.useCases.strategy.title",
        descriptionKey: "landing.useCases.strategy.description",
    },
    {
        icon: Lightbulb,
        titleKey: "landing.useCases.product.title",
        descriptionKey: "landing.useCases.product.description",
    },
    {
        icon: GitCompare,
        titleKey: "landing.useCases.technical.title",
        descriptionKey: "landing.useCases.technical.description",
    },
    {
        icon: FileText,
        titleKey: "landing.useCases.research.title",
        descriptionKey: "landing.useCases.research.description",
    },
]

export function SocialProof() {
    const { t } = useI18n()

    return (
        <section className="py-16 md:py-24" aria-labelledby="use-cases-heading">
            <div className="container mx-auto px-6">
                {/* Header */}
                <div className="mb-12 text-center">
                    <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-primary dark:text-blue-400">
                        {t("landing.useCases.label")}
                    </p>
                    <h2
                        id="use-cases-heading"
                        className="mb-4 font-heading text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
                    >
                        {t("landing.useCases.title")}
                    </h2>
                    <p className="mx-auto max-w-2xl text-lg text-slate-600 dark:text-slate-300">
                        {t("landing.useCases.subtitle")}
                    </p>
                </div>

                {/* Use Case Cards */}
                <div className="mb-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    {useCases.map((useCase, index) => {
                        const Icon = useCase.icon
                        return (
                            <div
                                key={index}
                                className="rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-md transition hover:-translate-y-1 hover:shadow-lg backdrop-blur-sm"
                            >
                                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                                    <Icon className="h-5 w-5" />
                                </div>
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                                    {t(useCase.titleKey)}
                                </h3>
                                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                                    {t(useCase.descriptionKey)}
                                </p>
                            </div>
                        )
                    })}
                </div>
            </div>
        </section>
    )
}
