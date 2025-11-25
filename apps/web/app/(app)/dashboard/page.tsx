import { redirect } from "next/navigation";
import DashboardClient from "./DashboardClient";
import type { DebateSummary } from "./types";
import { getMe } from "@/lib/auth";
import { getMyDebates } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const profile = await getMe();
  if (!profile) {
    redirect("/login?next=/dashboard");
  }

  return <DashboardClient email={profile?.email} />;
}
