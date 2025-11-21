"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Brain, MessageSquare, Vote } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";

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

  useEffect(() => {
    let cancelled = false;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
    if (user) {
      router.push("/dashboard");
    } else {
      router.push("/login?next=/dashboard");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2]">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute top-10 left-8 h-64 w-64 rounded-full bg-amber-200 blur-3xl opacity-30" />
        <div className="absolute top-40 right-12 h-80 w-80 rounded-full bg-[#d4c5a0] blur-3xl opacity-25" />
        <div className="absolute -bottom-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-amber-300 blur-3xl opacity-20" />
      </div>

      <div className="relative mx-auto flex max-w-6xl flex-col gap-12 px-6 py-16">
        <header className="flex items-center justify-between">
          <Link href="/home" className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:ring-offset-amber-50">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-200/50">
              <Brain className="h-6 w-6" />
            </div>
            <span className="text-2xl font-display font-bold text-[#3a2a1a]">Consultaion</span>
          </Link>
          <div className="flex items-center gap-3">
            {user ? (
              <Link
                href="/dashboard"
                className="rounded-lg border border-amber-200 bg-white px-4 py-2 text-sm font-semibold text-amber-900 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
              >
                {t("landing.nav.dashboard")}
              </Link>
            ) : (
              <Link
                href="/login"
                className="rounded-lg border border-amber-200 bg-white px-4 py-2 text-sm font-semibold text-amber-900 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
              >
                {t("landing.nav.signIn")}
              </Link>
            )}
          </div>
        </header>

        <section className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <h1 className="text-5xl font-display font-bold tracking-tight text-[#3a2a1a] leading-[1.1] sm:text-6xl md:leading-[1.05]">
              {t("landing.hero.title")}
              <span className="block bg-gradient-to-r from-amber-600 to-amber-400 bg-clip-text text-transparent">
                {t("landing.hero.accent")}
              </span>
            </h1>
            <p className="max-w-2xl text-lg text-[#5a4a3a]">{t("landing.hero.description")}</p>
            <div className="flex flex-col gap-2">
              <Button variant="amber" size="lg" className="w-fit px-8 focus-amber" onClick={handleStartDebate} disabled={loading}>
                {t("landing.hero.primaryCta")}
              </Button>
              {!user ? (
                <>
                  <Link href="/login?next=/dashboard" className="text-sm font-semibold text-amber-800 underline-offset-4 hover:underline">
                    {t("landing.hero.secondaryCta")}
                  </Link>
                  <p className="text-xs text-amber-900/70">{t("landing.hero.secondaryHint")}</p>
                </>
              ) : null}
            </div>
          </div>

          <div className="relative rounded-3xl border border-amber-100/80 bg-white/80 p-8 shadow-[0_20px_50px_rgba(112,73,28,0.12)] backdrop-blur">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-700">{t("landing.snapshot.caption")}</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <HeroStat label={t("landing.stats.agents")} value="8" />
              <HeroStat label={t("landing.stats.judges")} value="3" />
              <HeroStat label={t("landing.stats.rounds")} value="4" />
              <HeroStat label={t("landing.stats.synthesizer")} value="Online" />
            </div>
            <div className="mt-8 flex flex-col items-center gap-3">
              <ArcDots />
              <p className="max-w-sm text-center text-sm text-[#5a4a3a]">{t("landing.snapshot.description")}</p>
            </div>
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-3">
          {featureCards.map((card) => (
            <div
              key={card.titleKey}
              className="rounded-2xl border border-amber-100/80 bg-white/80 p-6 shadow-sm transition hover:-translate-y-[2px] hover:shadow-md"
            >
              <div className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-amber-100 to-amber-200 text-amber-700">
                {card.icon}
              </div>
              <h3 className="text-lg font-semibold text-[#3a2a1a]">{t(card.titleKey)}</h3>
              <p className="mt-2 text-sm text-[#5a4a3a]">{t(card.descriptionKey)}</p>
            </div>
          ))}
        </section>

        <DynamicLLMSelector />
      </div>
    </main>
  );
}

function LLMSelectorFallback() {
  const { t } = useI18n();
  return <div className="rounded-3xl border border-amber-100/70 bg-white/60 p-12 text-center text-sm text-[#5a4a3a]">{t("landing.model.loading")}</div>;
}

const DynamicLLMSelector = dynamic(() => import("@/components/ui/LLMSelector"), {
  ssr: false,
  loading: () => <LLMSelectorFallback />,
});

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-amber-100/80 bg-white p-4 text-left shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[#3a2a1a]">{value}</p>
    </div>
  );
}

function ArcDots() {
  return (
    <div className="relative h-40 w-72">
      <div className="absolute inset-0 rounded-full border border-amber-100/70 bg-gradient-to-b from-amber-50/60 to-white shadow-inner shadow-amber-200/40"></div>
      <div className="absolute left-1/2 top-4 flex -translate-x-1/2 gap-6">
        {[...Array(7)].map((_, idx) => (
          <span
            key={idx}
            className="h-2 w-2 rounded-full bg-amber-500"
            style={{ transform: `translateY(${Math.sin((idx / 6) * Math.PI) * 18}px)` }}
          />
        ))}
      </div>
      <div className="absolute inset-x-8 bottom-6 flex justify-between">
        {[...Array(6)].map((_, idx) => (
          <span key={idx} className="h-2 w-2 rounded-full bg-amber-300" />
        ))}
      </div>
    </div>
  );
}
