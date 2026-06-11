"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { BookOpen, Github } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { API_ORIGIN } from "@/lib/config/runtime";
import { Reveal } from "./Reveal";
import { HowItWorks } from "./HowItWorks";
import { ArenaAtAGlance } from "./ArenaAtAGlance";
import { ExampleReportPreview } from "./ExampleReportPreview";
import { DifferentiationSection } from "./DifferentiationSection";
import { UseCases } from "./UseCases";

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

  const handleStartArena = () => {
    if (loading) return;
    trackEvent("landing_hero_cta_clicked");
    if (user) {
      router.push("/live");
    } else {
      router.push("/login?next=/live");
    }
  };

  const scrollToReport = () => {
    trackEvent("landing_view_example_report_clicked");
    const el = document.getElementById("example-report-heading");
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <main className="relative min-h-screen overflow-x-clip bg-gradient-to-br from-slate-50 via-slate-100 to-amber-50/30 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900">
      {/* Background orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute top-10 left-8 h-64 w-64 rounded-full bg-amber-100 blur-3xl opacity-30 dark:bg-amber-500/10" />
        <div className="absolute top-40 right-12 h-80 w-80 rounded-full bg-amber-50 blur-3xl opacity-25 dark:bg-amber-500/5" />
        <div className="absolute -bottom-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-amber-200 blur-3xl opacity-15 dark:bg-amber-600/5" />
      </div>

      <div className="relative mx-auto flex max-w-6xl flex-col gap-0 px-6 py-8 md:py-16">
        {/* ─── SECTION 1: Hero ─── */}
        <section className="pb-16 md:pb-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            {/* Left: copy + CTAs */}
            <div className="space-y-6">
              <Reveal>
                <h1 className="text-4xl font-bold tracking-tight text-slate-900 dark:text-white leading-[1.1] sm:text-5xl lg:text-[3.4rem] lg:leading-[1.08]">
                  {t("landing.hero.title")}
                </h1>
              </Reveal>

              <Reveal delay={80}>
                <p className="max-w-xl text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                  {t("landing.hero.subtitle")}
                </p>
              </Reveal>

              <Reveal delay={160}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <Button
                    variant="default"
                    size="lg"
                    className="bg-amber-600 px-8 text-white shadow-lg shadow-amber-600/20 transition-all hover:bg-amber-700 hover:shadow-xl hover:shadow-amber-600/30 hover:-translate-y-[1px]"
                    onClick={handleStartArena}
                    disabled={loading}
                  >
                    {t("landing.hero.primaryCta")}
                  </Button>

                  <button
                    onClick={scrollToReport}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    {t("landing.hero.secondaryCta")}
                  </button>
                </div>
              </Reveal>

              {!user && !loading && (
                <Reveal delay={240}>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {t("landing.hero.secondaryHint")}
                  </p>
                </Reveal>
              )}
            </div>

            {/* Right: Parliament.png in premium frame */}
            <Reveal delay={200} direction="right" className="hidden lg:block">
              <div className="relative">
                {/* Ambient glow */}
                <div
                  className="absolute -inset-4 rounded-[32px] bg-amber-400/15 blur-3xl dark:bg-amber-500/10"
                  aria-hidden="true"
                />

                {/* Image container */}
                <div className="relative overflow-hidden rounded-[24px] border border-amber-200/50 bg-white/60 shadow-2xl shadow-amber-900/10 backdrop-blur dark:border-amber-700/30 dark:bg-slate-800/60 dark:shadow-amber-900/20">
                  <Image
                    src="/images/landing/Parliament.webp"
                    alt="A futuristic AI parliament chamber representing multiple AI models participating in a structured decision-making arena."
                    width={1600}
                    height={900}
                    priority
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="h-auto w-full object-cover"
                  />

                  {/* Gradient overlay */}
                  <div
                    className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/15 via-transparent to-white/5"
                    aria-hidden="true"
                  />

                  {/* Badge */}
                  <div className="absolute left-4 top-4 rounded-full border border-white/30 bg-white/20 px-3 py-1 text-[10px] font-semibold text-white/90 backdrop-blur-sm shadow-sm">
                    Multi-model decision arena
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ─── SECTION 2: How a Debate Works ─── */}
        <HowItWorks />

        {/* ─── SECTION 3: Arena at a Glance ─── */}
        <ArenaAtAGlance />

        {/* ─── SECTION 4: Example Decision Report ─── */}
        <ExampleReportPreview />

        {/* ─── SECTION 5: Why not just ask two models yourself? ─── */}
        <DifferentiationSection />

        {/* ─── SECTION 6: Use Cases ─── */}
        <UseCases />

        {/* ─── SECTION 7: Final CTA ─── */}
        <Reveal>
          <section className="relative z-10 mx-auto mb-12 flex max-w-2xl flex-col items-center gap-5 rounded-3xl border border-amber-200/50 bg-gradient-to-br from-amber-50/80 to-white/80 p-10 text-center shadow-xl shadow-amber-900/5 dark:border-amber-700/30 dark:from-slate-900/80 dark:to-slate-800/80 dark:shadow-none backdrop-blur">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white md:text-3xl">
              {t("landing.finalCta.title")}
            </h2>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                variant="default"
                size="lg"
                className="bg-amber-600 px-8 text-white shadow-lg shadow-amber-600/20 transition-all hover:bg-amber-700 hover:shadow-xl hover:shadow-amber-600/30"
                onClick={handleStartArena}
                disabled={loading}
              >
                {t("landing.finalCta.primary")}
              </Button>
              <button
                onClick={scrollToReport}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                {t("landing.finalCta.secondary")}
              </button>
            </div>
          </section>
        </Reveal>

        {/* Footer links */}
        <footer className="mt-4 flex flex-col items-center gap-6">
          <div className="flex flex-wrap justify-center gap-6 border-t border-slate-200 pt-6 dark:border-slate-800">
            <Link
              href="/docs"
              className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-amber-600 dark:text-slate-300 dark:hover:text-amber-400"
              onClick={() => trackEvent("landing_docs_clicked")}
            >
              <BookOpen className="h-4 w-4" />
              {t("landing.devs.docs")}
            </Link>
            <a
              href="https://github.com/kriptokasim/Consultaion"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-amber-600 dark:text-slate-300 dark:hover:text-amber-400"
              onClick={() => trackEvent("landing_github_clicked")}
            >
              <Github className="h-4 w-4" />
              {t("landing.devs.github")}
            </a>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-4 pb-8 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {marketingLinks.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="transition hover:text-amber-600"
              >
                {item.label}
              </Link>
            ))}
            <Link href="/terms" className="transition hover:text-amber-600">
              {t("footer.terms")}
            </Link>
            <Link href="/privacy" className="transition hover:text-amber-600">
              {t("footer.privacy")}
            </Link>
          </div>
        </footer>
      </div>
    </main>
  );
}
