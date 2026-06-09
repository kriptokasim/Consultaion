"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Brain, MessageSquare, Vote, BookOpen, Github } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import AnimatedCounter from "@/components/ui/AnimatedCounter";
import { MarketingHero } from "@/components/hero/marketing-hero";
import { trackEvent } from "@/lib/analytics";
import { SocialProof } from "@/components/landing/SocialProof";
import { API_ORIGIN } from "@/lib/config/runtime";

const featureCards = [
  {
    titleKey: "landing.feature.multi.title",
    descriptionKey: "landing.feature.multi.description",
    icon: <MessageSquare className="h-6 w-6" />,
  },
  {
    titleKey: "landing.feature.judges.title",
    descriptionKey: "landing.feature.judges.description",
    icon: <Vote className="h-6 w-6" />,
  },
  {
    titleKey: "landing.feature.synthesis.title",
    descriptionKey: "landing.feature.synthesis.description",
    icon: <Brain className="h-6 w-6" />,
  },
];

export default function HomeContent() {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const { t } = useI18n();
  const marketingLinks = [
    { href: "/pricing", label: t("nav.pricing") },
    { href: "/leaderboard", label: t("nav.leaderboard") },
    { href: "/hall-of-fame", label: t("nav.hallOfFame") },
    { href: "/models", label: t("nav.models") },
    { href: "/methodology", label: t("nav.methodology") },
  ];

  useEffect(() => {
    let cancelled = false;
    const apiBase = API_ORIGIN;
    fetch(`${apiBase}/me`, { credentials: "include", cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setUser(data);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleStartDebate = () => {
    if (loading) return;
    trackEvent("landing_hero_cta_clicked");
    if (user) {
      router.push("/live");
    } else {
      router.push("/login?next=/live");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-slate-100 to-indigo-50/50 dark:from-slate-900 dark:via-slate-950 dark:to-black">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute top-10 left-8 h-64 w-64 rounded-full bg-blue-100 blur-3xl opacity-30 dark:bg-blue-500/10" />
        <div className="absolute top-40 right-12 h-80 w-80 rounded-full bg-indigo-100 blur-3xl opacity-25 dark:bg-indigo-500/10" />
        <div className="absolute -bottom-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-blue-200 blur-3xl opacity-20 dark:bg-blue-600/10" />
      </div>

      <div className="relative mx-auto flex max-w-6xl flex-col gap-12 px-6 py-16">

        <MarketingHero>
          <div className="grid gap-12 px-6 py-16 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-6">
              <h1 className="text-5xl font-display font-bold tracking-tight text-slate-900 dark:text-white leading-[1.1] sm:text-6xl md:leading-[1.05]">
                Compare AI models. Find disagreement.
                <span className="block bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Get one stronger answer.
                </span>
              </h1>
              <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">The decision layer for multi-model AI.</p>
              <p className="max-w-2xl text-lg text-slate-600 dark:text-slate-300">Consultaion runs your question across multiple leading AI models, highlights where they agree or disagree, and synthesizes the strongest answer into a structured decision report.</p>
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap gap-3">
                  <Button variant="default" size="lg" className="px-8" onClick={handleStartDebate} disabled={loading}>
                    {t("landing.hero.primaryCta")}
                  </Button>
                  <Link
                    href="/demo"
                    onClick={() => trackEvent("landing_demo_cta_clicked")}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 px-6 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
                  >
                    {t("landing.hero.viewDemo")}
                  </Link>
                </div>
                {!user ? (
                  <>
                    <Link href="/login?next=/live" className="text-sm font-semibold text-primary dark:text-blue-400 underline-offset-4 hover:underline" onClick={() => trackEvent("landing_hero_secondary_cta_clicked")}>
                      {t("landing.hero.secondaryCta")}
                    </Link>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{t("landing.hero.secondaryHint")}</p>
                  </>
                ) : null}
              </div>
            </div>

            <div className="relative rounded-3xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/80 p-8 shadow-[0_20px_50px_rgba(30,58,95,0.06)] dark:shadow-none backdrop-blur">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary dark:text-blue-400">{t("landing.snapshot.caption")}</p>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <HeroStat label={t("landing.stats.agents")} value={8} animate />
                <HeroStat label={t("landing.stats.judges")} value={3} animate />
                <HeroStat label={t("landing.stats.rounds")} value={4} animate />
                <HeroStat label={t("landing.stats.synthesizer")} value={t("landing.stats.online")} />
              </div>
              <div className="mt-8 flex flex-col items-center gap-3">
                <ArcDots />
                <p className="max-w-sm text-center text-sm text-slate-600 dark:text-slate-300">{t("landing.snapshot.description")}</p>
              </div>
            </div>
          </div>
        </MarketingHero>

        <section className="space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-slate-900 dark:text-white">Why single-model answers are risky</h2>
            <p className="mt-4 text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">Single-model AI answers are often confident, incomplete, or wrong. Teams need a way to compare outputs, surface disagreement, and make better decisions.</p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="rounded-2xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:bg-white/80 dark:hover:bg-slate-800/80 hover:shadow-md">
                <h3 className="font-semibold text-slate-900 dark:text-white">{t(`landing.who.persona${i}.title`)}</h3>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t(`landing.who.persona${i}.description`)}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-slate-900 dark:text-white">{t("landing.features.title")}</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-primary dark:bg-blue-900/30 dark:text-blue-300">
                <MessageSquare className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t("landing.features.multi.title")}</h3>
              <p className="mt-2 mb-6 text-sm text-slate-600 dark:text-slate-300">{t("landing.features.multi.description")}</p>
              <Link href="/demo" className="text-sm font-semibold text-primary dark:text-blue-400 hover:underline">
                {t("landing.features.multi.cta")} →
              </Link>
            </div>

            <div className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-primary dark:bg-blue-900/30 dark:text-blue-300">
                <Vote className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t("landing.features.templates.title")}</h3>
              <p className="mt-2 mb-6 text-sm text-slate-600 dark:text-slate-300">{t("landing.features.templates.description")}</p>
              <button onClick={handleStartDebate} className="text-sm font-semibold text-primary dark:text-blue-400 hover:underline">
                {t("landing.features.templates.cta")} →
              </button>
            </div>

            <div className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-primary dark:bg-blue-900/30 dark:text-blue-300">
                <Brain className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t("landing.features.traces.title")}</h3>
              <p className="mt-2 mb-6 text-sm text-slate-600 dark:text-slate-300">{t("landing.features.traces.description")}</p>
              <Link href={user ? "/live" : "/login?next=/live"} className="text-sm font-semibold text-primary dark:text-blue-400 hover:underline">
                {t("landing.features.traces.cta")} →
              </Link>
            </div>
          </div>
        </section>

        {/* Why not just ask section */}
        <section className="space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-slate-900 dark:text-white">Why not just ask two models yourself?</h2>
            <p className="mt-4 text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">You could paste your question into ChatGPT and Claude separately. But you would miss what matters most: where they disagree, why they disagree, and what the strongest answer looks like when you combine their perspectives.</p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[
              { title: "Structured comparison", desc: "Run your question across multiple models in parallel with consistent evaluation criteria." },
              { title: "Disagreement surfaced", desc: "See exactly where models diverge — the signal that matters most for high-stakes decisions." },
              { title: "Decision report", desc: "Get a synthesized verdict with confidence, key findings, risks, and next actions — not raw chat text." },
              { title: "Audit trail", desc: "Every run is saved and shareable. Your team can review the reasoning behind any decision." },
              { title: "Consistent scoring", desc: "Models are evaluated on the same rubric every time, removing prompt-engineering variance." },
              { title: "Report-grade output", desc: "Export structured reports suitable for board decks, strategy docs, and team alignment." },
            ].map((item, i) => (
              <div key={i} className="rounded-2xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white">{item.title}</h3>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">            {item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it Works Section */}
        <section className="space-y-6">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-slate-900 dark:text-white">{t("landing.howItWorks.title")}</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((step) => (
              <div
                key={step}
                className="rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/50 p-6 shadow-sm transition hover:-translate-y-[2px] hover:shadow-md"
              >
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-100 to-indigo-150 text-lg font-bold text-primary dark:from-blue-600 dark:to-indigo-600 dark:text-white">
                  {step}
                </div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t(`landing.howItWorks.step${step}.title`)}</h3>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t(`landing.howItWorks.step${step}.description`)}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Demo CTA */}
        <section className="flex flex-col items-center gap-3 text-center">
          <Link
            href="/demo"
            onClick={() => trackEvent("landing_demo_cta_clicked")}
            className="group inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-600 px-8 py-4 text-lg font-semibold text-white shadow-[0_16px_40px_rgba(59,130,246,0.2)] transition hover:-translate-y-[2px] hover:shadow-[0_20px_50px_rgba(59,130,246,0.3)]"
          >
            <span className="text-lg font-semibold text-white">
              Try Interactive Demo
            </span>
            <span className="text-xs text-indigo-100">
              No sign up required
            </span>
          </Link>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            See how multi-model comparison works
          </p>
        </section>

        {/* Social Proof Section */}
        <SocialProof />

        <DynamicLLMSelector onStart={handleStartDebate} />

        <section className="relative z-10 mt-12 flex flex-col items-center gap-3 rounded-3xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/50 p-8 text-center shadow-[0_20px_50px_rgba(30,58,95,0.04)] dark:shadow-none">
          <p className="text-sm text-slate-600 dark:text-slate-300">{t("landing.footer.prompt")}</p>
          <Button variant="default" size="lg" className="px-8" onClick={handleStartDebate} disabled={loading}>
            {t("landing.selector.cta")}
          </Button>

          <div className="mt-8 flex flex-wrap justify-center gap-6 border-t border-slate-200 dark:border-slate-800 pt-6">
            <Link href="/docs" className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-primary dark:text-slate-300 dark:hover:text-blue-400" onClick={() => trackEvent("landing_docs_clicked")}>
              <BookOpen className="h-4 w-4" />
              {t("landing.devs.docs")}
            </Link>
            <a href="https://github.com/kriptokasim/Consultaion" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-primary dark:text-slate-300 dark:hover:text-blue-400" onClick={() => trackEvent("landing_github_clicked")}>
              <Github className="h-4 w-4" />
              {t("landing.devs.github")}
            </a>
          </div>
        </section>
        <footer className="mt-8 flex flex-wrap items-center justify-center gap-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {marketingLinks.map((item) => (
            <Link key={item.href} href={item.href} className="transition hover:text-primary">
              {item.label}
            </Link>
          ))}
          <Link href="/terms" className="transition hover:text-primary">
            {t("footer.terms")}
          </Link>
          <Link href="/privacy" className="transition hover:text-primary">
            {t("footer.privacy")}
          </Link>
        </footer>
      </div>
    </main>
  );
}

function LLMSelectorFallback() {
  const { t } = useI18n();
  return <div className="rounded-3xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/50 p-12 text-center text-sm text-slate-600 dark:text-slate-300">{t("landing.model.loading")}</div>;
}

const DynamicLLMSelector = dynamic<{ onStart?: () => void }>(() => import("@/components/ui/LLMSelector"), {
  ssr: false,
  loading: () => <LLMSelectorFallback />,
});

function HeroStat({ label, value, animate }: { label: string; value: string | number; animate?: boolean }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 p-4 text-left shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">
        {typeof value === "number" && animate ? <AnimatedCounter value={value} /> : value}
      </p>
    </div>
  );
}

function ArcDots() {
  return (
    <div className="relative h-40 w-72">
      <div className="absolute inset-0 rounded-full border border-slate-200 bg-gradient-to-b from-blue-50/60 to-white shadow-inner shadow-blue-200/40 dark:border-slate-700/70 dark:from-slate-800/60 dark:to-slate-900 dark:shadow-slate-900/40"></div>
      <div className="absolute left-1/2 top-4 flex -translate-x-1/2 gap-6">
        {[...Array(7)].map((_, idx) => (
          <span
            key={idx}
            className="h-2 w-2 rounded-full bg-blue-500 dark:bg-blue-400"
            style={{ transform: `translateY(${Math.sin((idx / 6) * Math.PI) * 18}px)` }}
          />
        ))}
      </div>
      <div className="absolute inset-x-8 bottom-6 flex justify-between">
        {[...Array(6)].map((_, idx) => (
          <span key={idx} className="h-2 w-2 rounded-full bg-blue-300 dark:bg-blue-500/60" />
        ))}
      </div>
    </div>
  );
}
