"use client"

import { useEffect, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Brain, Sparkles, Trophy, MessageSquare } from "lucide-react"
import { useI18n } from "@/lib/i18n/client"
import { DEMO_SCENARIOS } from "@/lib/mockDebateData"
import type { DemoScenario, MockDebateData } from "@/lib/mockDebateData"
import { trackEvent } from "@/lib/analytics"

export default function DemoPage() {
    const { t } = useI18n()
    const searchParams = useSearchParams()
    const router = useRouter()

    // Get scenario from URL or default to first
    const scenarioParam = searchParams.get("scenario")
    const [selectedScenarioId, setSelectedScenarioId] = useState<string>(
        scenarioParam && DEMO_SCENARIOS.find(s => s.id === scenarioParam)
            ? scenarioParam
            : DEMO_SCENARIOS[0].id
    )

    const selectedScenario = DEMO_SCENARIOS.find(s => s.id === selectedScenarioId) || DEMO_SCENARIOS[0]
    const debate = selectedScenario.data

    // Update URL when scenario changes
    const handleScenarioSelect = (scenarioId: string) => {
        setSelectedScenarioId(scenarioId)
        router.push(`/demo?scenario=${scenarioId}`, { scroll: false })
        trackEvent("demo_scenario_selected", { scenarioId })
    }

    // Sync with URL param changes
    useEffect(() => {
        if (scenarioParam && DEMO_SCENARIOS.find(s => s.id === scenarioParam)) {
            setSelectedScenarioId(scenarioParam)
        }
    }, [scenarioParam])

    return (
        <main className="min-h-screen bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] px-6 py-16">
            <div className="mx-auto max-w-5xl space-y-12">
                {/* Header */}
                <header className="space-y-6 text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border-2 border-dashed border-amber-300 bg-amber-50 px-4 py-1 text-sm font-semibold text-amber-700">
                        <Sparkles className="h-4 w-4" />
                        {t("demo.badge")}
                    </div>
                    <h1 className="text-4xl font-display font-bold text-[#3a2a1a]">
                        {t("demo.gallery.title")}
                    </h1>
                    <p className="mx-auto max-w-2xl text-lg text-[#5a4a3a]">
                        {t("demo.gallery.subtitle")}
                    </p>
                </header>

                {/* Scenario Selector */}
                <section className="space-y-4">
                    <h2 className="sr-only">Select a scenario</h2>
                    <div className="grid gap-4 md:grid-cols-3">
                        {DEMO_SCENARIOS.map((scenario) => (
                            <button
                                key={scenario.id}
                                onClick={() => handleScenarioSelect(scenario.id)}
                                className={`group relative overflow-hidden rounded-2xl border-2 p-5 text-left transition-all duration-200 ${selectedScenarioId === scenario.id
                                    ? "border-amber-500 bg-gradient-to-br from-amber-50 to-white shadow-lg scale-[1.02]"
                                    : "border-amber-200/70 bg-white/90 hover:border-amber-400 hover:shadow-md hover:-translate-y-[2px]"
                                    }`}
                            >
                                <div className="mb-3">
                                    <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${selectedScenarioId === scenario.id
                                        ? "bg-amber-500 text-white"
                                        : "bg-amber-100 text-amber-700"
                                        }`}>
                                        {t(`demo.tags.${scenario.tag.toLowerCase().replace(' & ', '')}`)}
                                    </span>
                                </div>
                                <h3 className="text-lg font-semibold text-[#3a2a1a] mb-2">
                                    {t(`demo.scenarios.${scenario.id.replace('-', '')}.title`)}
                                </h3>
                                <p className="text-sm text-[#5a4a3a]">
                                    {t(`demo.scenarios.${scenario.id.replace('-', '')}.description`)}
                                </p>
                                {selectedScenarioId === scenario.id && (
                                    <div className="absolute top-3 right-3">
                                        <div className="h-6 w-6 rounded-full bg-amber-500 flex items-center justify-center">
                                            <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                    </div>
                                )}
                            </button>
                        ))}
                    </div>
                </section>

                {/* Context */}
                <section className="rounded-2xl border border-amber-100/80 bg-white/90 p-6 shadow-sm">
                    <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-700">
                        {t("demo.context.label")}
                    </h2>
                    <p className="text-[#5a4a3a]">{debate.context}</p>
                </section>

                {/* Question */}
                <section className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-white to-amber-50/50 p-8 shadow-md">
                    <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber-700">
                        <MessageSquare className="h-4 w-4" />
                        {t("demo.question.label")}
                    </h2>
                    <p className="text-2xl font-semibold text-[#3a2a1a]">{debate.question}</p>
                </section>

                {/* Agents */}
                <section className="space-y-4">
                    <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("demo.agents.title")}</h2>
                    <div className="grid gap-4 md:grid-cols-3">
                        {debate.agents.map((agent) => (
                            <div
                                key={agent.id}
                                className="rounded-2xl border border-amber-100/80 bg-white/90 p-5 shadow-sm"
                            >
                                <div className="mb-2 flex items-center justify-between">
                                    <Brain className="h-5 w-5 text-amber-600" />
                                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                                        {agent.role}
                                    </span>
                                </div>
                                <h3 className="text-lg font-semibold text-[#3a2a1a]">{agent.name}</h3>
                                <p className="mt-1 text-sm text-amber-700">
                                    {agent.model} <span className="text-amber-600/70">• {agent.provider}</span>
                                </p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Debate Rounds */}
                <section className="space-y-6">
                    <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("demo.rounds.title")}</h2>
                    {debate.rounds.map((round) => (
                        <div key={round.number} className="space-y-4">
                            <h3 className="flex items-center gap-2 text-lg font-semibold text-amber-800">
                                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-amber-100 to-amber-200 text-sm font-bold text-amber-700">
                                    {round.number}
                                </span>
                                {t("demo.round.label")} {round.number}: {round.title}
                            </h3>
                            <div className="space-y-3">
                                {round.arguments.map((arg, idx) => (
                                    <div
                                        key={`${round.number}-${idx}`}
                                        className="rounded-xl border border-amber-100/70 bg-white/80 p-5 shadow-sm"
                                    >
                                        <div className="mb-2 font-semibold text-amber-900">{arg.agentName}</div>
                                        <p className="text-[#5a4a3a] leading-relaxed">{arg.content}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </section>

                {/* Judge Commentary */}
                <section className="space-y-4">
                    <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("demo.judges.title")}</h2>
                    <div className="space-y-3">
                        {debate.judgeCommentary.map((judge, idx) => (
                            <div
                                key={idx}
                                className="rounded-xl border border-slate-200/70 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm"
                            >
                                <div className="mb-2 flex items-center justify-between">
                                    <span className="font-semibold text-slate-800">{judge.judge}</span>
                                    <span className="text-sm font-medium text-amber-700">
                                        Leaning: {judge.leaning}
                                    </span>
                                </div>
                                <p className="text-slate-700 leading-relaxed">{judge.comment}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Champion Answer */}
                <section className="space-y-4">
                    <h2 className="flex items-center gap-2 text-2xl font-semibold text-[#3a2a1a]">
                        <Trophy className="h-6 w-6 text-amber-600" />
                        {t("demo.champion.title")}
                    </h2>
                    <div className="rounded-3xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 via-amber-100/50 to-white p-8 shadow-lg">
                        <div className="mb-4 flex items-center gap-3">
                            <div className="rounded-full bg-gradient-to-br from-amber-500 to-amber-600 px-4 py-1.5 text-sm font-bold text-white shadow-md">
                                {t("demo.champion.winner")}: {debate.championAnswer.winner}
                            </div>
                            <span className="text-sm text-amber-700">
                                ({debate.championAnswer.winnerModel})
                            </span>
                        </div>
                        <p className="mb-6 text-lg font-medium text-[#3a2a1a] leading-relaxed">
                            {debate.championAnswer.synthesis}
                        </p>
                        <div className="rounded-xl bg-white/80 p-5 border border-amber-200/70">
                            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-700">
                                {t("demo.champion.reasoning")}
                            </h4>
                            <p className="text-[#5a4a3a]">{debate.championAnswer.reasoning}</p>
                        </div>
                    </div>
                </section>

                {/* Footer CTAs */}
                <section className="flex flex-col items-center gap-4 rounded-3xl border border-amber-200/70 bg-white/90 p-8 text-center shadow-sm">
                    <p className="text-lg text-[#5a4a3a]">
                        Ready to run your own debate with real AI models?
                    </p>
                    <div className="flex flex-wrap justify-center gap-4">
                        <Link
                            href="/login?next=/dashboard"
                            onClick={() => trackEvent("demo_run_own_question_clicked", { scenarioId: selectedScenarioId })}
                            className="rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-8 py-3 font-semibold text-white shadow-md transition hover:-translate-y-[1px] hover:shadow-lg"
                        >
                            {t("demo.cta.primary")}
                        </Link>
                        <Link
                            href="/"
                            className="rounded-lg border-2 border-amber-300 bg-white px-8 py-3 font-semibold text-amber-900 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
                        >
                            {t("demo.cta.secondary")}
                        </Link>
                    </div>
                </section>
            </div>
        </main>
    )
}
