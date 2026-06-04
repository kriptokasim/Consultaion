"use client";

import Link from "next/link";
import { Play, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const GALLERY_ITEMS = [
  {
    id: "demo",
    title: "Startup Strategy",
    prompt: "Should a B2B SaaS startup prioritize growth or profitability in its first 12 months?",
    modelsCount: 4,
    synthesisPreview: "Do not prioritize absolute profitability in year one, but do not pursue reckless growth either. Prioritize efficient, repeatable growth. Spend your first 12 months proving that your unit economics work.",
  },
  {
    id: "demo",
    title: "Technical Architecture",
    prompt: "Compare PostgreSQL, MongoDB, and DynamoDB for a high-write, low-latency analytics application.",
    modelsCount: 4,
    synthesisPreview: "While MongoDB offers flexibility and DynamoDB scales infinitely, PostgreSQL with TimescaleDB or partitioning is often the safest bet for structured analytics unless write velocity exceeds 10k/sec.",
  },
  {
    id: "demo",
    title: "Marketing Strategy",
    prompt: "What is the most effective go-to-market strategy for an open-source developer tool?",
    modelsCount: 4,
    synthesisPreview: "Product-led growth (PLG) driven by a strong bottom-up adoption model is essential. Offer a frictionless open-source version, build a passionate community on Discord/GitHub, and monetize via hosted cloud versions or enterprise SSO.",
  }
];

export default function GalleryClient() {
  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 px-6 py-16">
      <div className="mx-auto max-w-5xl space-y-12">
        <header className="space-y-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-100 dark:bg-blue-900/30 px-4 py-1 text-sm font-semibold text-blue-700 dark:text-blue-300">
            <Sparkles className="h-4 w-4" />
            Curated Examples
          </div>
          <h1 className="text-4xl font-display font-bold text-slate-900 dark:text-white">
            See the power of multi-model AI
          </h1>
          <p className="mx-auto max-w-2xl text-lg text-slate-600 dark:text-slate-300">
            Explore how different AI models disagree, and how Consultaion synthesizes them into actionable decision artifacts.
          </p>
        </header>

        <section className="grid gap-6">
          {GALLERY_ITEMS.map((item, idx) => (
            <div
              key={idx}
              className="flex flex-col md:flex-row gap-6 rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:shadow-md"
            >
              <div className="flex-1 space-y-4">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                    {item.title}
                  </span>
                  <span className="text-xs text-slate-500">
                    {item.modelsCount} Models Compared
                  </span>
                </div>
                <h3 className="text-xl font-semibold text-slate-900 dark:text-white">
                  &quot;{item.prompt}&quot;
                </h3>
                <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4 border border-slate-100 dark:border-slate-800">
                  <p className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-1">Synthesis Preview</p>
                  <p className="text-slate-600 dark:text-slate-300 leading-relaxed italic">
                    &quot;{item.synthesisPreview}&quot;
                  </p>
                </div>
              </div>
              <div className="flex flex-col justify-center gap-3 shrink-0 md:w-48 border-t md:border-t-0 md:border-l border-slate-100 dark:border-slate-800 pt-4 md:pt-0 md:pl-6">
                <Button asChild className="w-full">
                  <Link href={`/demo`}>
                    View Arena Run
                  </Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`/login?next=${encodeURIComponent(`/live?prefill_prompt_from=demo`)}`}>
                    <Play className="h-4 w-4 mr-2" />
                    Run similar
                  </Link>
                </Button>
              </div>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
