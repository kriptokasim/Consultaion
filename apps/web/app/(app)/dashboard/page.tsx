import { redirect } from "next/navigation";
import DashboardClient from "./DashboardClient";
import type { DebateSummary } from "./types";
import { getMe } from "@/lib/auth";
import { getMyDebates } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage(props: { searchParams: Promise<{ token?: string }> }) {
  const searchParams = await props.searchParams;
  const token = searchParams?.token;

  let profile = null;
  // If token is present, we skip server-side auth check to allow client to bootstrap session
  if (!token) {
    profile = await getMe();
    if (!profile) {
      redirect("/login?next=/dashboard");
    }
  }

  return <DashboardClient email={profile?.email} authToken={token} />;
}
