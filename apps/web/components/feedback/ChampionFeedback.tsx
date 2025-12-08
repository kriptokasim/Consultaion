"use client"

import { useState } from "react"
import { useI18n } from "@/lib/i18n/client"
import { ThumbsUp, ThumbsDown } from "lucide-react"
import { trackEvent } from "@/lib/analytics"

interface ChampionFeedbackProps {
    source: "demo" | "app"
    scenarioId?: string
    debateId?: string
}

export function ChampionFeedback({ source, scenarioId, debateId }: ChampionFeedbackProps) {
    const { t } = useI18n()
    const [feedback, setFeedback] = useState<boolean | null>(null)
    const [showThanks, setShowThanks] = useState(false)

    const handleFeedback = (helpful: boolean) => {
        setFeedback(helpful)
        setShowThanks(true)

        // Track event
        trackEvent("champion_feedback", {
            helpful,
            source,
            ...(scenarioId && { scenarioId }),
            ...(debateId && { debateId }),
        })

        // Hide thanks message after 3 seconds
        setTimeout(() => setShowThanks(false), 3000)
    }

    return (
        <div className="flex items-center gap-4 rounded-lg border border-amber-200 bg-amber-50/50 px-4 py-3">
            {/* Question */}
            <span className="text-sm font-medium text-[#3a2a1a]">
                {t("feedback.champion.question")}
            </span>

            {/* Buttons */}
            <div className="flex gap-2">
                <button
                    onClick={() => handleFeedback(true)}
                    disabled={feedback !== null}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${feedback === true
                            ? "bg-green-500 text-white"
                            : "bg-white text-[#3a2a1a] hover:bg-amber-100 disabled:opacity-50"
                        }`}
                    aria-label={t("feedback.champion.yes")}
                >
                    <ThumbsUp className="h-4 w-4" aria-hidden="true" />
                    <span>{t("feedback.champion.yes")}</span>
                </button>

                <button
                    onClick={() => handleFeedback(false)}
                    disabled={feedback !== null}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${feedback === false
                            ? "bg-red-500 text-white"
                            : "bg-white text-[#3a2a1a] hover:bg-amber-100 disabled:opacity-50"
                        }`}
                    aria-label={t("feedback.champion.no")}
                >
                    <ThumbsDown className="h-4 w-4" aria-hidden="true" />
                    <span>{t("feedback.champion.no")}</span>
                </button>
            </div>

            {/* Thanks Message */}
            {showThanks && (
                <span className="text-sm italic text-green-700">
                    {t("feedback.champion.thanks")}
                </span>
            )}
        </div>
    )
}
