import { redirect } from "next/navigation";
import DashboardClient from "./DashboardClient";
import { getMe } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const profile = await getMe();
  if (!profile) {
    redirect("/login?next=/live");
  }

  return <DashboardClient email={profile.email} />;
}
