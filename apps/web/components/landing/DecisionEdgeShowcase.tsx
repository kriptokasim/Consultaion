"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, GitBranch, Sparkles, Trophy } from "lucide-react";

export function DecisionEdgeShowcase() {
  return (
    <section className="py-8 md:py-14" aria-labelledby="decision-edge-heading">
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="relative overflow-hidden rounded-[28px] border border-amber-200/70 bg-slate-950 p-6 text-white shadow-2xl shadow-amber-900/10 md:p-8">
          <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-amber-400/20 blur-3xl" aria-hidden="true" />
          <div className="relative">
            <div className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">
              <GitBranch className="h-4 w-4" />
              The Consultaion edge
            </div>
            <h2 id="decision-edge-heading" className="max-w-2xl text-3xl font-bold leading-tight md:text-4xl">
              Don&apos;t just collect answers. See where the models disagree.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 md:text-base">
              Consultaion compares independent frontier-model perspectives, isolates the assumptions that split them, and turns disagreement into a decision signal.
            </p>

            <div className="mt-7 rounded-2xl border border-white/10 bg-white/[0.06] p-4 md:p-5">
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Example question</p>
                  <p className="mt-1 text-sm font-semibold text-white md:text-base">Should we launch this product now?</p>
                </div>
                <div className="shrink-0 rounded-full border border-rose-400/30 bg-rose-400/10 px-3 py-1 text-xs font-bold text-rose-200">
                  68% divergence
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                {[
                  ["GPT-5.6", "Launch", "Demand is strong enough."],
                  ["Claude", "Hold", "Runway risk is too high."],
                  ["Gemini", "Launch", "Timing advantage outweighs risk."],
                  ["Grok", "Hold", "Distribution is not ready."],
                ].map(([model, stance, reason]) => (
                  <div key={model} className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-white">{model}</span>
                      <span className="text-[10px] font-bold uppercase tracking-wide text-amber-300">{stance}</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-5 text-slate-400">{reason}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-2 rounded-xl border border-amber-300/20 bg-amber-300/5 px-3 py-2.5 text-xs text-amber-100">
                <Sparkles className="h-4 w-4 shrink-0" />
                <span><strong>Why they disagree:</strong> two models assume low execution risk; two assume the opposite.</span>
              </div>
            </div>

            <Link
              href="/demo"
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-amber-400"
            >
              See a live example
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-1">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Self-check</p>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Verified reports</h3>
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
              The final report is checked against the underlying model responses for faithfulness and completeness before it is marked verified.
            </p>
            <div className="mt-4 flex items-center gap-3 text-xs font-semibold text-slate-500 dark:text-slate-400">
              <span>Faithfulness</span><span>94%</span><span className="text-slate-300 dark:text-slate-700">•</span><span>Completeness</span><span>91%</span>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-300">
                <Trophy className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Prediction loop</p>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Lock. Reveal. Learn.</h3>
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
              Pick a winner before the verdict, lock your confidence, then compare your prediction with the models and the crowd when the result resolves.
            </p>
            <div className="mt-4 inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-300">
              Your prediction → outcome → accuracy
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 dark:border-slate-800 dark:bg-slate-900/40">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-500">Debate</p>
          <h3 className="mt-2 text-xl font-bold text-slate-900 dark:text-white">The dramatic entry point.</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Personas, rounds, judges, predictions and a reveal. Built to be watched, challenged and shared.</p>
          <Link href="/demo" className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-rose-600 hover:text-rose-700 dark:text-rose-400">
            Challenge the models <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="rounded-3xl border border-amber-200 bg-amber-50/60 p-6 dark:border-amber-900/40 dark:bg-amber-950/10">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-600 dark:text-amber-400">Arena</p>
          <h3 className="mt-2 text-xl font-bold text-slate-900 dark:text-white">The serious decision engine.</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Independent model perspectives, semantic divergence, synthesis and a defensible decision brief for work that matters.</p>
          <Link href="/live" className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-amber-700 hover:text-amber-800 dark:text-amber-300">
            Make a better decision <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
