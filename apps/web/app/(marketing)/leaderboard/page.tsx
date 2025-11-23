import LeaderboardTable from "@/components/parliament/LeaderboardTable";
import Brand from "@/components/parliament/Brand";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import { ApiError, getLeaderboard, getRateLimitInfo, isAuthError } from "@/lib/api";
import { redirect } from "next/navigation";
import { getServerTranslations } from "@/lib/i18n/server";

type LeaderboardPageProps = {
  searchParams: Promise<{ category?: string; min_matches?: string }>;
};

export const dynamic = "force-dynamic";

export default async function LeaderboardPage({ searchParams }: LeaderboardPageProps) {
  const { t } = await getServerTranslations();
  const params = (await searchParams) || {};
  const category = params.category ?? undefined;
  const minMatches = params.min_matches ? parseInt(params.min_matches, 10) || 0 : 0;

  let items: Awaited<ReturnType<typeof getLeaderboard>> = [];
  let rateLimitNotice: { detail: string; resetAt?: string } | null = null;
  let errorMessage: string | null = null;
  try {
    items = await getLeaderboard({
      category: category === "all" ? undefined : category,
      minMatches: minMatches || undefined,
      limit: 100,
    });
  } catch (error) {
    if (error instanceof ApiError) {
      const info = getRateLimitInfo(error);
      if (info) {
        rateLimitNotice = info;
      } else if (isAuthError(error)) {
        redirect("/login");
      } else {
        errorMessage = t("leaderboard.error.short");
      }
    } else {
      errorMessage = t("leaderboard.error.long");
    }
  }

  const categories = Array.from(new Set(items.map((entry) => entry.category).filter(Boolean))) as string[];

  return (
    <main id="main" className="space-y-6 p-4">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-stone-50 via-white to-amber-50 p-6 shadow">
        <div className="flex items-center gap-3">
          <Brand height={32} tone="amber" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("leaderboard.kicker")}</p>
            <h1 className="text-3xl font-semibold text-stone-900">{t("leaderboard.title")}</h1>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-stone-600">{t("leaderboard.description")}</p>
      </header>
      {rateLimitNotice ? (
        <RateLimitBanner detail={rateLimitNotice.detail} resetAt={rateLimitNotice.resetAt} />
      ) : null}
      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        {errorMessage ? (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            {errorMessage}
          </div>
        ) : null}
        <form className="flex flex-wrap items-center gap-4 text-sm text-stone-600" method="get">
          <label className="flex items-center gap-2">
            {t("leaderboard.filters.category")}
            <select
              name="category"
              defaultValue={category ?? "all"}
              className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-1.5 text-sm text-stone-900"
            >
              <option value="all">{t("leaderboard.filters.categoryAll")}</option>
              <option value="">{t("leaderboard.filters.categoryNone")}</option>
              {categories.map((cat) => (
                <option key={cat} value={cat ?? ""}>
                  {cat}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            {t("leaderboard.filters.minMatches")}
            <input
              type="number"
              name="min_matches"
              min={0}
              defaultValue={minMatches || 0}
              className="w-24 rounded-lg border border-stone-200 bg-stone-50 px-3 py-1.5 text-sm text-stone-900"
            />
          </label>
          <button
            type="submit"
            className="inline-flex items-center gap-2 rounded-full bg-amber-600 px-4 py-1.5 text-sm font-semibold text-white shadow hover:bg-amber-500"
          >
            {t("leaderboard.filters.submit")}
          </button>
          <a href="/methodology" className="text-xs font-semibold uppercase tracking-wide text-amber-600">
            {t("leaderboard.filters.methodology")} →
          </a>
        </form>
        <div className="mt-6">
          <LeaderboardTable items={items} />
        </div>
        <p className="mt-3 text-xs text-stone-500">{t("leaderboard.footer.note")}</p>
      </section>
    </main>
  );
}
