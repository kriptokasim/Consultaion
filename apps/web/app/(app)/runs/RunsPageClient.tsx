'use client';

import RunsTable from "@/components/consultaion/consultaion/runs-table";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import SmartSearch from "@/components/parliament/SmartSearch";
import RunsShowcase from "@/components/parliament/RunsShowcase";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { useQuery } from "@tanstack/react-query";
import { getMe } from "@/lib/auth";
import { ApiError, getRateLimitInfo, isAuthError, getTeams } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n/client";

type RunsPageClientProps = {
    initialQuery: string;
    initialStatus: string;
};

export default function RunsPageClient({ initialQuery, initialStatus }: RunsPageClientProps) {
    const router = useRouter();
    const { t } = useI18n();

    const { data: debatesData, isLoading: isLoadingDebates, error: debatesError } = useDebatesList({
        limit: 100,
        offset: 0,
        q: initialQuery || undefined,
        status: initialStatus || undefined,
    });

    const { data: profile, isLoading: isLoadingProfile } = useQuery({
        queryKey: ['me'],
        queryFn: getMe,
        retry: false,
        staleTime: 30000,
    });

    const { data: teams } = useQuery({
        queryKey: ['teams'],
        queryFn: () => getTeams().catch(() => []),
        staleTime: 60000,
    });

    const [profileState, setProfileState] = useState<"loading" | "loaded" | "unavailable">("loading");
    const profileTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const profileResolvedRef = useRef(false);

    useEffect(() => {
        if (profileResolvedRef.current) return;
        if (isLoadingProfile) {
            profileTimeoutRef.current = setTimeout(() => {
                if (!profileResolvedRef.current) {
                    setProfileState("unavailable");
                    profileResolvedRef.current = true;
                }
            }, 5000);
        } else {
            profileResolvedRef.current = true;
            setProfileState(profile ? "loaded" : "unavailable");
            if (profileTimeoutRef.current) {
                clearTimeout(profileTimeoutRef.current);
                profileTimeoutRef.current = null;
            }
        }
        return () => {
            if (profileTimeoutRef.current) {
                clearTimeout(profileTimeoutRef.current);
            }
        };
    }, [isLoadingProfile, profile]);

    useEffect(() => {
        if (debatesError && isAuthError(debatesError)) {
            router.push('/login');
        }
    }, [debatesError, router]);

    const debatesListReady = !!debatesData && !isLoadingDebates;
    const showContent = debatesListReady || isLoadingDebates;

    let rateLimitNotice: { detail: string; resetAt?: string } | null = null;
    if (debatesError instanceof ApiError) {
        const info = getRateLimitInfo(debatesError);
        if (info) rateLimitNotice = info;
    }

    const items = rateLimitNotice ? [] : (debatesData?.items ?? []);
    const searchItems = items.map((item) => ({
      id: item.id,
      prompt: item.prompt ?? "",
      mode: item.mode ?? null,
      status: item.status ?? null,
      title: null,
      createdAt: item.created_at ?? null,
    }));

    const effectiveProfile = profileState === "loaded" ? profile : null;
    const effectiveTeams = teams ?? [];

    if (!showContent) {
        return <div className="flex h-screen items-center justify-center text-slate-600 dark:text-slate-300">Loading...</div>;
    }

    return (
        <main id="main" className="h-full space-y-8 py-6">
            <header className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 via-white to-amber-50/70 p-6 shadow-[0_24px_60px_#1e3a5f14] dark:border-slate-700 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700 dark:text-amber-400">{t("runs.hero.kicker")}</p>
                <div className="mt-1 flex flex-wrap items-center gap-3">
                    <h1 className="heading-serif text-3xl font-semibold text-slate-900 dark:text-white">{t("runs.hero.title")}</h1>
                    <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700 shadow-inner shadow-slate-900/5 dark:border-slate-600 dark:bg-slate-800 dark:text-white">
                        {t("runs.hero.badge")}
                    </span>
                </div>
                <p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
                    {t("runs.hero.description")}
                </p>
            </header>

            <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <SmartSearch items={searchItems} initialQuery={initialQuery} />
                <div className="rounded-2xl border border-slate-200 bg-white/85 p-4 shadow-[0_18px_40px_#1e3a5f14] dark:border-slate-700 dark:bg-slate-800">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700 dark:text-amber-400">{t("runs.status.kicker")}</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-slate-700 dark:text-slate-300">
                        <div className="rounded-xl border border-slate-200 bg-amber-50 p-3 shadow-inner shadow-slate-900/5 dark:border-slate-600 dark:bg-slate-700">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("runs.status.total")}</p>
                            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-white">{items.length}</p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-amber-50 p-3 shadow-inner shadow-slate-900/5 dark:border-slate-600 dark:bg-slate-700">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("runs.status.inProgress")}</p>
                            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-white">
                                {items.filter((item) => item.status === "running").length}
                            </p>
                        </div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                        {t("runs.status.note")}
                    </p>
                </div>
            </section>

            {rateLimitNotice ? (
                <RateLimitBanner detail={rateLimitNotice.detail} resetAt={rateLimitNotice.resetAt} />
            ) : null}

            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700 dark:text-amber-400">{t("runs.list.kicker")}</p>
                        <h2 className="heading-serif text-xl font-semibold text-slate-900 dark:text-white">{t("runs.list.title")}</h2>
                    </div>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{t("runs.list.caption")}</span>
                </div>
                <RunsShowcase runs={items} />
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-[0_18px_40px_#1e3a5f14] dark:border-slate-700 dark:bg-slate-800">
                {profileState === "loading" && (
                    <div className="text-xs text-amber-600 mb-2">Loading profile...</div>
                )}
                <RunsTable
                    items={items}
                    teams={effectiveTeams}
                    profile={effectiveProfile}
                    initialQuery={initialQuery}
                    initialStatus={initialStatus || null}
                />
            </section>
        </main>
    );
}
