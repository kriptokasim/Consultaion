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

  const payload = await getMyDebates({ limit: 8, offset: 0 }).catch(() => ({ items: [] }));
  const items = Array.isArray(payload?.items) ? (payload.items as DebateSummary[]) : [];

  return <DashboardClient initialDebates={items} email={profile?.email} />;
}
