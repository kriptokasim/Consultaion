import { getMe } from "@/lib/auth"
import { redirect } from "next/navigation"
import { getServerTranslations } from "@/lib/i18n/server"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { PrivacySettings } from "@/components/settings/privacy-settings"
import { MilestoneCelebration } from "@/components/settings/milestone-celebration"
import { ThemeToggle } from "@/components/settings/theme-toggle"

export default async function SettingsPage() {
  const { t } = await getServerTranslations()
  const profile = await getMe()
  if (!profile) {
    redirect("/login?next=/settings")
  }
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-700 dark:text-amber-400">{t("settings.overview.kicker")}</p>
        <h1 className="heading-serif text-3xl font-semibold text-slate-900 dark:text-white">{t("settings.overview.title")}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t("settings.overview.description")}
        </p>
      </div>
      <div className="card-elevated max-w-2xl space-y-3 p-6">
        <p className="heading-serif text-lg font-semibold text-slate-900 dark:text-white">{t("settings.overview.cardTitle")}</p>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t("settings.overview.cardParagraph1")}
        </p>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t("settings.overview.cardParagraph2")}
        </p>
      </div>

      <ThemeToggle />

      <NotificationSettings initialEnabled={profile.email_summaries_enabled} />
      <PrivacySettings initialOptOut={profile.analytics_opt_out} />
      <MilestoneCelebration debateCount={profile.debate_count || 0} />
    </div>
  )
}
