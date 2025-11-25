'use client';

import RunsTable from "@/components/consultaion/consultaion/runs-table";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import SmartSearch from "@/components/parliament/SmartSearch";
import RunsShowcase from "@/components/parliament/RunsShowcase";
import { useDebatesList } from "@/lib/api/hooks/useDebatesList";
import { useQuery } from "@tanstack/react-query";
import { getMe } from "@/lib/auth";
import { ApiError, getRateLimitInfo, isAuthError, getTeams } from "@/lib/api";
import { redirect, useRouter } from "next/navigation";
import { useEffect } from "react";

type RunsPageClientProps = {
    initialQuery: string;
    initialStatus: string;
    translations: Record<string, string>;
};

export default function RunsPageClient({ initialQuery, initialStatus, translations }: RunsPageClientProps) {
    const router = useRouter();
    const t = (key: string) => translations[key] || key;

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
    });

    const { data: teams } = useQuery({
        queryKey: ['teams'],
        queryFn: () => getTeams().catch(() => []),
    });

    useEffect(() => {
        if (debatesError && isAuthError(debatesError)) {
            // Handle auth redirect if needed, or let the interceptor handle it
            // For now, we can redirect manually
            router.push('/login');
        }
    }, [debatesError, router]);

    if (isLoadingDebates || isLoadingProfile) {
        return <div className="flex h-screen items-center justify-center">Loading...</div>;
    }

    // Handle rate limit from error if possible, but useDebatesList might not expose the error object directly in a way we can parse easily if it's wrapped.
    // Assuming debatesError is the ApiError.
    let rateLimitNotice: { detail: string; resetAt?: string } | null = null;
    if (debatesError instanceof ApiError) {
        const info = getRateLimitInfo(debatesError);
        if (info) rateLimitNotice = info;
    }

    const items = rateLimitNotice ? [] : debatesData?.items ?? [];
    const searchItems = items.map((item) => ({ id: item.id, prompt: item.prompt ?? "" }));

    return (
        <main id="main" className="h-full space-y-8 py-6">
            <header className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_24px_60px_rgba(112,73,28,0.14)] dark:border-amber-900/50 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">{t("runs.hero.kicker")}</p>
                <div className="mt-1 flex flex-wrap items-center gap-3">
                    <h1 className="heading-serif text-3xl font-semibold text-amber-900 dark:text-amber-50">{t("runs.hero.title")}</h1>
                    <span className="rounded-full border border-amber-200/70 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
                        {t("runs.hero.badge")}
                    </span>
                </div>
                <p className="mt-2 max-w-3xl text-sm text-stone-700 dark:text-amber-50/80">
                    {t("runs.hero.description")}
                </p>
            </header>

            <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <SmartSearch items={searchItems} initialQuery={initialQuery} />
                <div className="rounded-2xl border border-amber-200/70 bg-white/85 p-4 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-800 dark:text-amber-200">{t("runs.status.kicker")}</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-stone-700 dark:text-amber-50/80">
                        <div className="rounded-xl border border-amber-100/80 bg-amber-50/80 p-3 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200">{t("runs.status.total")}</p>
                            <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-50">{items.length}</p>
                        </div>
                        <div className="rounded-xl border border-amber-100/80 bg-amber-50/80 p-3 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200">{t("runs.status.inProgress")}</p>
                            <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-50">
                                {items.filter((item) => item.status === "running").length}
                            </p>
                        </div>
                    </div>
                    <p className="mt-3 text-xs text-stone-600 dark:text-amber-100/70">
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
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">{t("runs.list.kicker")}</p>
                        <h2 className="heading-serif text-xl font-semibold text-amber-900 dark:text-amber-50">{t("runs.list.title")}</h2>
                    </div>
                    <span className="text-xs text-stone-600 dark:text-amber-100/70">{t("runs.list.caption")}</span>
                </div>
                <RunsShowcase runs={items} />
            </section>

            <section className="rounded-3xl border border-amber-200/70 bg-white/90 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/50 dark:bg-stone-900/70">
                <RunsTable
                    items={items}
                    teams={teams || []}
                    profile={profile}
                    initialQuery={initialQuery}
                    initialStatus={initialStatus || null}
                />
            </section>
        </main>
    );
}
