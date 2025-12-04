import { getMe } from "@/lib/auth"
import { redirect } from "next/navigation"
import { getServerTranslations } from "@/lib/i18n/server"
import { NotificationSettings } from "@/components/settings/notification-settings"

export default async function SettingsPage() {
  const { t } = await getServerTranslations()
  const profile = await getMe()
  if (!profile) {
    redirect("/login?next=/settings")
  }
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-600">{t("settings.overview.kicker")}</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950">{t("settings.overview.title")}</h1>
        <p className="text-sm text-amber-900/70 dark:text-amber-100/70">
          {t("settings.overview.description")}
        </p>
      </div>
      <div className="card-elevated max-w-2xl space-y-3 p-6">
        <p className="text-base font-semibold text-amber-950 dark:text-amber-50">{t("settings.overview.cardTitle")}</p>
        <p className="text-sm text-amber-900/80 dark:text-amber-100/80">
          {t("settings.overview.cardParagraph1")}
        </p>
        <p className="text-sm text-amber-900/80 dark:text-amber-100/80">
          {t("settings.overview.cardParagraph2")}
        </p>
      </div>

      <NotificationSettings initialEnabled={profile.email_summaries_enabled} />
    </div>
  )
}
