"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/client";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { Reveal } from "./Reveal";
import { cn } from "@/lib/utils";
import {
  MessageSquareText,
  GitCompareArrows,
  AlertTriangle,
  FileCheck2,
} from "lucide-react";

const stepIcons = [MessageSquareText, GitCompareArrows, AlertTriangle, FileCheck2];

// Step 1: prompt card
function PromptVisual({ active }: { active: boolean }) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-5 shadow-md transition-all duration-500 dark:border-slate-700 dark:bg-slate-800",
        active
          ? "border-amber-300 shadow-amber-200/40 dark:shadow-amber-500/10 scale-100"
          : "border-slate-200 opacity-60 scale-95"
      )}
    >
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
        Your question
      </div>
      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
        &ldquo;Should we enter the European market this quarter or wait for
        stronger demand signals?&rdquo;
      </p>
    </div>
  );
}

// Step 2: model response cards
function ModelResponsesVisual({ active }: { active: boolean }) {
  return (
    <div className="space-y-2">
      {["GPT-4o", "Claude 3.5", "Gemini Pro"].map((model, i) => (
        <div
          key={model}
          className={cn(
            "rounded-xl border bg-white p-3 shadow-sm transition-all dark:border-slate-700 dark:bg-slate-800",
            active
              ? "border-amber-200 opacity-100 translate-x-0"
              : "border-slate-200 opacity-40 translate-x-2",
            "duration-500"
          )}
          style={{ transitionDelay: active ? `${i * 100}ms` : "0ms" }}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {model}
          </span>
          <div className="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                i === 0
                  ? "bg-emerald-400 w-4/5"
                  : i === 1
                    ? "bg-blue-400 w-3/5"
                    : "bg-purple-400 w-7/12"
              )}
              style={{ transitionDelay: active ? `${i * 150 + 200}ms` : "0ms" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// Step 3: divergence meter
function DivergenceVisual({ active }: { active: boolean }) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-5 shadow-md transition-all duration-500 dark:border-slate-700 dark:bg-slate-800",
        active
          ? "border-amber-300 shadow-amber-200/40 dark:shadow-amber-500/10"
          : "border-slate-200 opacity-60"
      )}
    >
      <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
        Divergence analysis
      </div>
      <div className="space-y-2">
        {[
          { label: "Consensus", value: 72, color: "bg-emerald-400" },
          { label: "Disagreement", value: 28, color: "bg-red-400" },
        ].map((item) => (
          <div key={item.label}>
            <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
              <span>{item.label}</span>
              <span className="font-semibold">{item.value}%</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  item.color
                )}
                style={{ width: active ? `${item.value}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Step 4: decision report card
function DecisionReportVisual({ active }: { active: boolean }) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-5 shadow-md transition-all duration-500 dark:border-slate-700 dark:bg-slate-800",
        active
          ? "border-amber-300 shadow-amber-200/40 dark:shadow-amber-500/10"
          : "border-slate-200 opacity-60"
      )}
    >
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
        Decision report
      </div>
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
          <FileCheck2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            Proceed with a narrow pilot
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Confidence: 78% · 3 risks identified
          </p>
        </div>
      </div>
    </div>
  );
}

const stepVisuals = [PromptVisual, ModelResponsesVisual, DivergenceVisual, DecisionReportVisual];

export function HowItWorks() {
  const { t } = useI18n();
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const stepsContainerRef = useRef<HTMLDivElement | null>(null);
  const prefersReducedMotion = useReducedMotion();

  const steps = [
    {
      title: t("landing.howItWorks.steps.ask.title"),
      description: t("landing.howItWorks.steps.ask.description"),
    },
    {
      title: t("landing.howItWorks.steps.compare.title"),
      description: t("landing.howItWorks.steps.compare.description"),
    },
    {
      title: t("landing.howItWorks.steps.divergence.title"),
      description: t("landing.howItWorks.steps.divergence.description"),
    },
    {
      title: t("landing.howItWorks.steps.report.title"),
      description: t("landing.howItWorks.steps.report.description"),
    },
  ];

  // Phase 2: Click handler for step cards
  const handleStepClick = useCallback(
    (index: number) => {
      setActiveStep(index);
      const el = stepRefs.current[index];
      if (!el) return;

      el.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "center",
      });
    },
    [prefersReducedMotion]
  );

  // Phase 4: Scroll-progress-based active step detection (desktop only)
  useEffect(() => {
    if (prefersReducedMotion) return;

    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    let raf = 0;
    let scrollBound = false;

    const updateActiveStep = () => {
      const container = stepsContainerRef.current;
      if (!container) return;

      const cards = stepRefs.current.filter(Boolean) as HTMLElement[];
      if (!cards.length) return;

      // If at the bottom of the page, activate the last step
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 60) {
        setActiveStep(cards.length - 1);
        return;
      }

      const viewportAnchor = window.innerHeight * 0.5;

      let bestIndex = 0;
      let bestDistance = Number.POSITIVE_INFINITY;

      cards.forEach((card, index) => {
        const rect = card.getBoundingClientRect();
        const cardCenter = rect.top + rect.height / 2;
        const distance = Math.abs(cardCenter - viewportAnchor);

        if (distance < bestDistance) {
          bestDistance = distance;
          bestIndex = index;
        }
      });

      setActiveStep((prev) => (prev === bestIndex ? prev : bestIndex));
    };

    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(updateActiveStep);
    };

    const bindScroll = () => {
      if (scrollBound) return;
      scrollBound = true;
      updateActiveStep();
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onScroll);
    };

    const unbindScroll = () => {
      if (!scrollBound) return;
      scrollBound = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };

    const handleBreakpointChange = (e: MediaQueryListEvent) => {
      if (e.matches) {
        bindScroll();
      } else {
        unbindScroll();
      }
    };

    // Initial bind if already desktop
    if (desktopQuery.matches) {
      bindScroll();
    }

    desktopQuery.addEventListener("change", handleBreakpointChange);

    return () => {
      unbindScroll();
      desktopQuery.removeEventListener("change", handleBreakpointChange);
    };
  }, [prefersReducedMotion]);

  const ActiveVisual = stepVisuals[activeStep];

  return (
    <section
      className="relative overflow-visible py-16 md:py-24"
      aria-labelledby="how-it-works-heading"
    >
      <Reveal>
        <div className="mb-12 text-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            {t("landing.howItWorks.subtitle")}
          </p>
          <h2
            id="how-it-works-heading"
            className="text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
          >
            {t("landing.howItWorks.title")}
          </h2>
        </div>
      </Reveal>

      <div className="mx-auto max-w-6xl px-4 md:px-6">
        {/* Desktop: two-column with sticky visual */}
        <div className="hidden lg:grid lg:grid-cols-[0.9fr_1.1fr] lg:items-start lg:gap-14">
          {/* Left: sticky visual — Phase 4 stabilization */}
          <aside className="sticky top-28 z-10 self-start">
            <div className="max-h-[calc(100vh-8rem)] rounded-3xl border border-slate-200/70 bg-white/70 p-4 shadow-xl backdrop-blur dark:border-slate-800 dark:bg-slate-900/70">
              <ActiveVisual active={true} />
            </div>
          </aside>

          {/* Right: interactive step cards */}
          <div ref={stepsContainerRef} className="space-y-10 pb-16 xl:pb-20">
            {/* Progress rail */}
            <div className="mb-6 flex items-center gap-2" aria-hidden="true">
              {steps.map((_, index) => (
                <div
                  key={`progress-${index}`}
                  className={cn(
                    "h-1 flex-1 rounded-full transition-colors duration-300",
                    index <= activeStep ? "bg-amber-500" : "bg-slate-200 dark:bg-slate-800"
                  )}
                />
              ))}
            </div>

            {steps.map((step, index) => {
              const Icon = stepIcons[index];
              return (
                <button
                  key={step.title}
                  type="button"
                  ref={(el) => {
                    stepRefs.current[index] = el;
                  }}
                  onClick={() => handleStepClick(index)}
                  aria-current={activeStep === index ? "step" : undefined}
                  className={cn(
                    "w-full min-h-[220px] scroll-mt-32 rounded-2xl border p-6 text-left transition-all duration-300",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2",
                    activeStep === index
                      ? "border-amber-300 bg-amber-50/60 shadow-md dark:border-amber-600/40 dark:bg-amber-950/20"
                      : "border-slate-200 bg-white/60 hover:border-amber-200 hover:bg-white dark:border-slate-800 dark:bg-slate-900/40 dark:hover:border-slate-700"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors duration-300",
                        activeStep === index
                          ? "bg-amber-500 text-white"
                          : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                        Step {index + 1}
                      </div>
                      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                        {step.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        {step.description}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Mobile: simple stacked cards — Phase 8 */}
        <div className="space-y-6 lg:hidden">
          {steps.map((step, index) => {
            const Icon = stepIcons[index];
            return (
              <Reveal key={`mobile-${step.title}`} delay={index * 100}>
                <div className="rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/50">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                        Step {index + 1}
                      </div>
                      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                        {step.title}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        {step.description}
                      </p>
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
