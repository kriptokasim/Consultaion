import BillingSettingsClient from "@/components/billing/BillingSettingsClient";
import { getMe } from "@/lib/auth";
import { redirect } from "next/navigation";

export default async function BillingSettingsPage() {
  const profile = await getMe();
  if (!profile) {
    redirect("/login?next=/settings/billing");
  }
  return <BillingSettingsClient />;
}
