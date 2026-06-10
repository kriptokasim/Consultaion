"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "./Reveal";
import { cn } from "@/lib/utils";
import { API_ORIGIN } from "@/lib/config/runtime";
import { Activity, FileText, Cpu, TrendingUp } from "lucide-react";

interface PublicStats {
  completed_runs: number;
  reports_generated: number;
  active_models: number;
  avg_divergence_score?: number | null;
}

function AnimatedCount({ value, suffix }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement | null>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const prefersReduced =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setDisplay(value);
      return;
    }

    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const duration = 1200;
          const start = performance.now();
          const animate = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplay(Math.round(eased * value));
            if (progress < 1) requestAnimationFrame(animate);
          };
          requestAnimationFrame(animate);
          observer.disconnect();
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [value]);

  return (
    <span ref={ref}>
      {display.toLocaleString()}
      {suffix}
    </span>
  );
}

function MetricSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl border border-slate-200 bg-white/60 p-6 dark:border-slate-800 dark:bg-slate-900/40">
      <div className="h-4 w-16 rounded bg-slate-200 dark:bg-slate-700" />
      <div className="mt-3 h-8 w-20 rounded bg-slate-200 dark:bg-slate-700" />
    </div>
  );
}

export function ArenaAtAGlance() {
  const { t } = useI18n();
  const [stats, setStats] = useState<PublicStats | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiBase = API_ORIGIN;
    fetch(`${apiBase}/public/stats`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Failed"))))
      .then((data: PublicStats) => {
        setStats(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const hasData = stats && (stats.completed_runs > 0 || stats.reports_generated > 0);

  const metrics = stats
    ? [
        {
          icon: Activity,
          label: t("landing.arenaAtAGlance.metrics.completedRuns"),
          value: stats.completed_runs,
        },
        {
          icon: FileText,
          label: t("landing.arenaAtAGlance.metrics.reportsGenerated"),
          value: stats.reports_generated,
        },
        {
          icon: Cpu,
          label: t("landing.arenaAtAGlance.metrics.activeModels"),
          value: stats.active_models,
        },
        ...(stats.avg_divergence_score != null
          ? [
              {
                icon: TrendingUp,
                label: t("landing.arenaAtAGlance.metrics.averageDivergence"),
                value: stats.avg_divergence_score,
                suffix: "%",
              },
            ]
          : []),
      ]
    : [];

  return (
    <section className="py-16 md:py-24" aria-labelledby="arena-glance-heading">
      <Reveal>
        <div className="mb-12 text-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            {t("landing.arenaAtAGlance.subtitle")}
          </p>
          <h2
            id="arena-glance-heading"
            className="text-3xl font-bold text-slate-900 dark:text-white md:text-4xl"
          >
            {t("landing.arenaAtAGlance.title")}
          </h2>
        </div>
      </Reveal>

      {loading ? (
        <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      ) : error || !hasData ? (
        <Reveal>
          <div className="mx-auto max-w-lg rounded-2xl border border-dashed border-slate-300 bg-white/60 p-8 text-center dark:border-slate-700 dark:bg-slate-900/40">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {error
                ? t("landing.arenaAtAGlance.error")
                : t("landing.arenaAtAGlance.empty")}
            </p>
          </div>
        </Reveal>
      ) : (
        <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric, index) => {
            const Icon = metric.icon;
            return (
              <Reveal key={index} delay={index * 100}>
                <div className="rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-900/50 backdrop-blur-sm">
                  <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
                    <Icon className="h-4 w-4" />
                  </div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {metric.label}
                  </p>
                  <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">
                    <AnimatedCount
                      value={metric.value}
                      suffix={"suffix" in metric ? (metric as any).suffix : undefined}
                    />
                  </p>
                </div>
              </Reveal>
            );
          })}
        </div>
      )}
    </section>
  );
}
