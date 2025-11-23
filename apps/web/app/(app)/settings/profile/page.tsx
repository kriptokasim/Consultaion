import ProfileSettings from "@/components/settings/profile-settings"
import { getMe } from "@/lib/auth"
import { redirect } from "next/navigation"

export default async function ProfileSettingsPage() {
  const profile = await getMe()
  if (!profile) {
    redirect("/login?next=/settings/profile")
  }
  return (
    <div className="space-y-6">
      <ProfileSettings />
    </div>
  )
}
