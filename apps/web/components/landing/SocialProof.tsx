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
                    <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-700">
                        {t("landing.socialProof.label")}
                    </p>
                    <h2
                        id="social-proof-heading"
                        className="mb-4 font-heading text-3xl font-bold text-[#3a2a1a] md:text-4xl"
                    >
                        {t("landing.socialProof.title")}
                    </h2>
                    <p className="mx-auto max-w-2xl text-lg text-[#5a4a3a]">
                        {t("landing.socialProof.subtitle")}
                    </p>
                </div>

                {/* Testimonial Cards */}
                <div className="mb-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {testimonials.map((testimonial, index) => (
                        <div
                            key={index}
                            className="rounded-2xl border border-amber-200/70 bg-white p-6 shadow-md transition hover:-translate-y-1 hover:shadow-lg"
                        >
                            {/* Quote Icon */}
                            <div className="mb-4 flex items-center justify-between">
                                <Quote className="h-8 w-8 text-amber-500" aria-hidden="true" />
                            </div>

                            {/* Quote Text */}
                            <blockquote className="mb-4 text-base italic leading-relaxed text-[#3a2a1a]">
                                "{testimonial.quote}"
                            </blockquote>

                            {/* Attribution */}
                            <div className="border-t border-amber-100 pt-4">
                                <p className="font-semibold text-[#3a2a1a]">{testimonial.name}</p>
                                <p className="text-sm text-[#5a4a3a]">{testimonial.role}</p>
                                <p className="text-xs text-amber-700">{testimonial.companyType}</p>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Used By Tags */}
                <div className="flex flex-wrap items-center justify-center gap-3">
                    <span className="text-sm font-medium text-[#5a4a3a]">
                        {t("landing.socialProof.usedBy")}:
                    </span>
                    {tags.map((tag, index) => (
                        <span
                            key={index}
                            className="rounded-full border border-amber-300 bg-amber-50 px-4 py-1.5 text-sm font-medium text-amber-900"
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
