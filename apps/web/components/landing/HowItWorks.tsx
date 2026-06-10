"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "./Reveal";
import { cn } from "@/lib/utils";
import {
  MessageSquareText,
  GitCompareArrows,
  AlertTriangle,
  FileCheck2,
} from "lucide-react";

const stepIcons = [MessageSquareText, GitCompareArrows, AlertTriangle, FileCheck2];

const stepVisuals = [
  // Step 1: prompt card
  ({ active }: { active: boolean }) => (
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
  ),
  // Step 2: model response cards
  ({ active }: { active: boolean }) => (
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
  ),
  // Step 3: divergence meter
  ({ active }: { active: boolean }) => (
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
                  item.color,
                  active ? `w-[${item.value}%]` : "w-0"
                )}
                style={{ width: active ? `${item.value}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  ),
  // Step 4: decision report card
  ({ active }: { active: boolean }) => (
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
  ),
];

export function HowItWorks() {
  const { t } = useI18n();
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const prefersReduced =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) return;

    const observers: IntersectionObserver[] = [];

    stepRefs.current.forEach((el, index) => {
      if (!el) return;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveStep(index);
          }
        },
        { threshold: 0.6 }
      );
      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

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

  const ActiveVisual = stepVisuals[activeStep];

  return (
    <section className="py-16 md:py-24" aria-labelledby="how-it-works-heading">
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

      <div className="mx-auto max-w-5xl">
        {/* Desktop: two-column with sticky visual */}
        <div className="hidden lg:grid lg:grid-cols-[1fr_1.1fr] lg:gap-12">
          {/* Left: sticky visual */}
          <div className="relative">
            <div className="sticky top-32">
              <ActiveVisual active={true} />
            </div>
          </div>

          {/* Right: step cards */}
          <div className="space-y-8">
            {steps.map((step, index) => {
              const Icon = stepIcons[index];
              return (
                <div
                  key={index}
                  ref={(el) => {
                    stepRefs.current[index] = el;
                  }}
                  className={cn(
                    "rounded-2xl border p-6 transition-all duration-300",
                    activeStep === index
                      ? "border-amber-300 bg-amber-50/60 shadow-md dark:border-amber-600/40 dark:bg-amber-950/20"
                      : "border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/40"
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
                </div>
              );
            })}
          </div>
        </div>

        {/* Mobile: simple stacked cards */}
        <div className="space-y-6 lg:hidden">
          {steps.map((step, index) => {
            const Icon = stepIcons[index];
            return (
              <Reveal key={index} delay={index * 100}>
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
