"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"
import { ArrowLeft, Key, Database, Shield, FileText, Users } from "lucide-react"

const items = [
  { nameKey: "settings.nav.overview", href: "/settings" },
  { nameKey: "settings.nav.profile", href: "/settings/profile" },
  { nameKey: "settings.nav.billing", href: "/settings/billing" },
  { nameKey: "settings.nav.apiAccess", href: "/settings/api-access", icon: Key },
  { nameKey: "settings.nav.providerKeys", href: "/settings/provider-keys", icon: Database },
  { nameKey: "settings.nav.auditLogs", href: "/settings/audit-logs", icon: FileText },
  { nameKey: "settings.nav.dataRetention", href: "/settings/data-retention", icon: Shield },
  { nameKey: "settings.nav.team", href: "/settings/team", icon: Users },
]

export default function SettingsNav() {
  const pathname = usePathname()
  const { t } = useI18n()
  return (
    <nav className="card-elevated space-y-1 p-5">
      <Link
        href="/live"
        className="mb-4 flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition hover:text-amber-700 dark:text-slate-400 dark:hover:text-amber-400"
      >
        <ArrowLeft className="h-3 w-3" />
        {t("settings.nav.backToArena")}
      </Link>
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">{t("settings.nav.title")}</p>
      <div className="mt-3 space-y-1 text-sm font-semibold text-slate-600 dark:text-slate-300">
        {items.map((item) => {
          const active = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.nameKey}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-xl px-3 py-2 transition-all",
                active
                  ? "bg-amber-100 text-amber-800 shadow-inner shadow-amber-200 dark:bg-amber-900/50 dark:text-amber-200"
                  : "text-slate-600 hover:bg-amber-50 hover:text-amber-800 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white",
              )}
            >
              {Icon && <Icon className="h-3.5 w-3.5" />}
              {t(item.nameKey)}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
