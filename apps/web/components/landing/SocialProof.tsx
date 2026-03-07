"use client"

import { useI18n } from "@/lib/i18n/client"
import { Quote } from "lucide-react"

export function SocialProof() {
    const { t } = useI18n()

    const testimonials = [
        {
            quote: t("landing.socialProof.testimonials.1.quote"),
            name: t("landing.socialProof.testimonials.1.name"),
            role: t("landing.socialProof.testimonials.1.role"),
            companyType: t("landing.socialProof.testimonials.1.companyType"),
        },
        {
            quote: t("landing.socialProof.testimonials.2.quote"),
            name: t("landing.socialProof.testimonials.2.name"),
            role: t("landing.socialProof.testimonials.2.role"),
            companyType: t("landing.socialProof.testimonials.2.companyType"),
        },
        {
            quote: t("landing.socialProof.testimonials.3.quote"),
            name: t("landing.socialProof.testimonials.3.name"),
            role: t("landing.socialProof.testimonials.3.role"),
            companyType: t("landing.socialProof.testimonials.3.companyType"),
        },
    ]

    const tags = [
        t("landing.socialProof.tags.saas"),
        t("landing.socialProof.tags.consulting"),
        t("landing.socialProof.tags.research"),
    ]

    return (
        <section className="py-16 md:py-24" aria-labelledby="social-proof-heading">
            <div className="container mx-auto px-6">
                {/* Header */}
                <div className="mb-12 text-center">
                    <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                        {t("landing.socialProof.label")}
                    </p>
                    <h2
                        id="social-proof-heading"
                        className="mb-4 font-heading text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
                    >
                        {t("landing.socialProof.title")}
                    </h2>
                    <p className="mx-auto max-w-2xl text-lg text-slate-600 dark:text-slate-300">
                        {t("landing.socialProof.subtitle")}
                    </p>
                </div>

                {/* Testimonial Cards */}
                <div className="mb-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {testimonials.map((testimonial, index) => (
                        <div
                            key={index}
                            className="rounded-2xl border border-amber-200/70 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-md transition hover:-translate-y-1 hover:shadow-lg"
                        >
                            {/* Quote Icon */}
                            <div className="mb-4 flex items-center justify-between">
                                <Quote className="h-8 w-8 text-amber-500 dark:text-amber-400" aria-hidden="true" />
                            </div>

                            {/* Quote Text */}
                            <blockquote className="mb-4 text-base italic leading-relaxed text-slate-900 dark:text-slate-100">
                                &quot;{testimonial.quote}&quot;
                            </blockquote>

                            {/* Attribution */}
                            <div className="border-t border-amber-100 dark:border-slate-800 pt-4">
                                <p className="font-semibold text-slate-900 dark:text-white">{testimonial.name}</p>
                                <p className="text-sm text-slate-600 dark:text-slate-400">{testimonial.role}</p>
                                <p className="text-xs text-amber-700 dark:text-amber-400">{testimonial.companyType}</p>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Used By Tags */}
                <div className="flex flex-wrap items-center justify-center gap-3">
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                        {t("landing.socialProof.usedBy")}:
                    </span>
                    {tags.map((tag, index) => (
                        <span
                            key={index}
                            className="rounded-full border border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/30 px-4 py-1.5 text-sm font-medium text-amber-900 dark:text-amber-200"
                        >
                            {tag}
                        </span>
                    ))}
                </div>

                {/* TODO: Replace with CMS-sourced testimonials and real company logos */}
            </div>
        </section>
    )
}
