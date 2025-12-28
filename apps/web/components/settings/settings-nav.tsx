"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"

const items = [
  { nameKey: "settings.nav.overview", href: "/settings" },
  { nameKey: "settings.nav.profile", href: "/settings/profile" },
  { nameKey: "settings.nav.billing", href: "/settings/billing" },
]

export default function SettingsNav() {
  const pathname = usePathname()
  const { t } = useI18n()
  return (
    <nav className="card-elevated space-y-1 p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary dark:text-blue-400">{t("settings.nav.title")}</p>
      <div className="mt-3 space-y-1 text-sm font-semibold text-slate-600 dark:text-slate-300">
        {items.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.nameKey}
              href={item.href}
              className={cn(
                "block rounded-xl px-3 py-2 transition-all",
                active
                  ? "bg-blue-100 text-blue-800 shadow-inner shadow-blue-200 dark:bg-blue-900/50 dark:text-blue-200"
                  : "text-slate-600 hover:bg-blue-50 hover:text-blue-800 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white",
              )}
            >
              {t(item.nameKey)}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
