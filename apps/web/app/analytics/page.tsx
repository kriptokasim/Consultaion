import AnalyticsDashboard, { AnalyticsActivityItem, AnalyticsData, AnalyticsWinRate } from "@/components/parliament/AnalyticsDashboard";
import { getMyDebates } from "@/lib/api";
import { getMe } from "@/lib/auth";

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
  const profile = await getMe();
  if (!profile) {
    return (
      <main id="main" className="flex h-full items-center justify-center py-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">Sign in to view analytics.</p>
          <a href="/login" className="mt-3 inline-flex items-center rounded bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Go to Login
          </a>
        </div>
      </main>
    );
  }
  const data = await getMyDebates({ limit: 100 });
  const analytics = buildAnalytics(data?.items ?? []);
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
