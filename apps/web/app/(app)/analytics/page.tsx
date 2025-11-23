import AnalyticsDashboard, { AnalyticsActivityItem, AnalyticsData, AnalyticsWinRate } from "@/components/parliament/AnalyticsDashboard";
import { getMyDebates } from "@/lib/api";
import { getMe } from "@/lib/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getServerTranslations } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

type DebateRecord = {
  id: string;
  prompt: string;
  status: string;
  created_at: string;
  updated_at: string;
  final_meta?: {
    ranking?: string[];
    scores?: { persona: string; score: number; rationale?: string }[];
  };
};

export default async function AnalyticsPage() {
  const { t } = await getServerTranslations();
  const profile = await getMe();
  if (!profile) {
    redirect("/login?next=/analytics");
  }
  const data = await getMyDebates({ limit: 100 });
  const analytics = buildAnalytics(data?.items ?? []);
  if (!analytics.totals.debates) {
    return (
      <main id="main" className="flex h-full items-center justify-center p-6">
        <div className="space-y-3 rounded-3xl border border-amber-200/70 bg-white p-6 text-center shadow-sm">
          <h2 className="text-xl font-semibold text-stone-900">{t("analytics.empty.overviewTitle")}</h2>
          <p className="text-sm text-stone-600">{t("analytics.empty.overviewDescription")}</p>
          <Link
            href="/live"
            className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-amber-500"
          >
            {t("analytics.empty.cta")}
          </Link>
        </div>
      </main>
    );
  }
  return (
    <main id="main" className="space-y-6 p-4">
      <AnalyticsDashboard data={analytics} />
    </main>
  );
}

function buildAnalytics(debates: DebateRecord[]): AnalyticsData {
  const total = debates.length;
  const completed = debates.filter((debate) => debate.status?.startsWith("completed")).length;
  const completionRate = total ? completed / total : 0;

  const avgDurationMinutes =
    debates.reduce((acc, debate) => {
      const start = debate.created_at ? new Date(debate.created_at).getTime() : 0;
      const end = debate.updated_at ? new Date(debate.updated_at).getTime() : start;
      return acc + Math.max(0, end - start);
    }, 0) /
      (total || 1) /
      1000 /
      60 || 0;

  const winMap = new Map<string, AnalyticsWinRate>();
  debates.forEach((debate) => {
    const winner = debate.final_meta?.ranking?.[0];
    if (!winner) return;
    const entry = winMap.get(winner) ?? { persona: winner, wins: 0, total: 0 };
    entry.wins += 1;
    entry.total += 1;
    winMap.set(winner, entry);
    debate.final_meta?.ranking?.slice(1).forEach((persona) => {
      const loserEntry = winMap.get(persona) ?? { persona, wins: 0, total: 0 };
      loserEntry.total += 1;
      winMap.set(persona, loserEntry);
    });
  });

  const scoreBuckets = [
    { label: "0‒2", count: 0, min: 0, max: 2 },
    { label: "2‒4", count: 0, min: 2, max: 4 },
    { label: "4‒6", count: 0, min: 4, max: 6 },
    { label: "6‒8", count: 0, min: 6, max: 8 },
    { label: "8‒10", count: 0, min: 8, max: 10.1 },
  ];

  debates.forEach((debate) => {
    debate.final_meta?.scores?.forEach((score) => {
      const bucket = scoreBuckets.find((item) => score.score >= item.min && score.score < item.max);
      if (bucket) bucket.count += 1;
    });
  });

  const activity: AnalyticsActivityItem[] = debates
    .slice()
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 8)
    .map((debate) => ({
      id: debate.id,
      title: debate.prompt.slice(0, 90),
      timestamp: debate.updated_at || debate.created_at,
      status: debate.status,
    }));

  const analyticsData: AnalyticsData = {
    totals: {
      debates: total,
      completed,
      completionRate,
      avgDurationMinutes,
    },
    winRates: Array.from(winMap.values()).sort((a, b) => b.wins - a.wins),
    scoreDistribution: scoreBuckets,
    activity,
  };

  return analyticsData;
}
