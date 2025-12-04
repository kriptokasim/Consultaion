"use client"

import { type ComponentType, useState } from "react"
import { ArrowRight, Brain, Sparkles, Zap } from "lucide-react"

import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"
import { getModelAvatarUrl } from "@/lib/avatar"

type ModelCard = {
  id: string
  name: string
  descriptionKey: string
  icon: ComponentType<{ className?: string }>
  gradient: string
  glow: string
}

const models: ModelCard[] = [
  {
    id: "gpt4o",
    name: "GPT‑4o",
    descriptionKey: "landing.selector.models.gpt4o",
    icon: Sparkles,
    gradient: "from-sky-400 via-blue-500 to-indigo-600",
    glow: "shadow-sky-400/40",
  },
  {
    id: "claude35",
    name: "Claude 3.5",
    descriptionKey: "landing.selector.models.claude35",
    icon: Brain,
    gradient: "from-amber-400 via-rose-500 to-pink-600",
    glow: "shadow-rose-400/40",
  },
  {
    id: "gemini",
    name: "Gemini Pro",
    descriptionKey: "landing.selector.models.gemini",
    icon: Zap,
    gradient: "from-emerald-400 via-teal-500 to-cyan-500",
    glow: "shadow-emerald-400/40",
  },
]

export default function LLMSelector({ onStart }: { onStart?: () => void }) {
  const [selected, setSelected] = useState(models[0].id)
  const { t } = useI18n()

  return (
    <section className="relative mt-12 w-full overflow-hidden rounded-[36px] bg-neutral-950 px-6 py-14 text-white shadow-[0_50px_140px_-80px_rgba(15,15,15,0.9)]">
      <div className="pointer-events-none absolute inset-0 opacity-40">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.35),_transparent_55%)]" />
      </div>

      <div className="relative mx-auto flex max-w-5xl flex-col items-center text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-white/60">{t("landing.selector.caption")}</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          {t("landing.selector.title")}
        </h2>
        <p className="mt-4 max-w-2xl text-base text-white/70">
          {t("landing.selector.description")}
        </p>
      </div>

      <div className="relative mx-auto mt-12 grid w-full max-w-5xl gap-6 md:grid-cols-3">
        {models.map((model) => {
          const Icon = model.icon
          const isSelected = selected === model.id
          return (
            <button
              key={model.id}
              type="button"
              onClick={() => setSelected(model.id)}
              className={cn(
                "group relative overflow-hidden rounded-3xl border border-white/10 bg-neutral-900/50 p-6 text-left transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
                isSelected
                  ? cn(
                    "scale-105 border-white/30 shadow-2xl",
                    model.glow,
                    "bg-neutral-900/90",
                  )
                  : "hover:-translate-y-1 hover:bg-neutral-900/80",
              )}
            >
              {isSelected && (
                <div
                  className={cn(
                    "pointer-events-none absolute inset-0 opacity-15 blur-3xl",
                    `bg-gradient-to-br ${model.gradient}`,
                  )}
                />
              )}
              <div className="relative z-[1] flex flex-col items-start gap-4">
                <div
                  className={cn(
                    "flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-lg transition-all duration-300 group-hover:scale-110 group-hover:rotate-3",
                    `bg-gradient-to-br ${model.gradient}`,
                  )}
                >
                  {getModelAvatarUrl(model.name) ? (
                    <img
                      src={getModelAvatarUrl(model.name)!}
                      alt={model.name}
                      className="h-8 w-8 rounded-full bg-white/10 p-0.5"
                    />
                  ) : (
                    <Icon className="h-6 w-6" />
                  )}
                </div>
                <div>
                  <p className="text-lg font-semibold">{model.name}</p>
                  <p className="mt-1 text-sm text-white/70">{t(model.descriptionKey)}</p>
                </div>
                <div
                  className={cn(
                    "h-1 rounded-full bg-gradient-to-r transition-all duration-300",
                    model.gradient,
                    isSelected ? "w-12 opacity-100" : "w-0 opacity-0",
                  )}
                />
              </div>
            </button>
          )
        })}
      </div>

      <div className="relative mt-10 flex justify-center">
        <button
          type="button"
          onClick={onStart}
          className="group inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-8 py-3 text-sm font-semibold text-white shadow-[0_25px_60px_-20px_rgba(255,255,255,0.6)] transition-all duration-200 hover:scale-105 active:scale-95"
        >
          {t("landing.selector.cta")}
          <ArrowRight className="h-4 w-4 transition-all duration-200 group-hover:translate-x-1" />
        </button>
      </div>
    </section>
  )
}
