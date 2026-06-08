import { getMe } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getServerTranslations } from "@/lib/i18n/server";
import ParticipationClient from "./ParticipationClient";

export const dynamic = "force-dynamic";

export default async function ParticipationPage() {
  const { t } = await getServerTranslations();
  const profile = await getMe();
  
  if (!profile) {
    redirect("/login?next=/participation");
  }

  return <ParticipationClient profile={profile} />;
}
