import { getHallOfFame, getLeaderboard, getModelLeaderboard } from "@/lib/api";
import { ModelRegistrySurface } from "@/components/marketing/broadsheet/registry/ModelRegistrySurface";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Model Registry",
  description:
    "The full model registry: real win rates and average scores, the ranked leaderboard, and the hall of fame of decisive runs.",
};

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const [modelStats, leaderboard, hallOfFameResponse] = await Promise.all([
    getModelLeaderboard().catch(() => []),
    getLeaderboard({ limit: 100 }).catch(() => []),
    getHallOfFame({}).catch(() => ({ items: [] })),
  ]);

  return (
    <ModelRegistrySurface
      modelStats={modelStats}
      leaderboard={leaderboard}
      hallOfFame={hallOfFameResponse.items}
    />
  );
}
