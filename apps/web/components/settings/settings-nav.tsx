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
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("settings.nav.title")}</p>
      <div className="mt-3 space-y-1 text-sm font-semibold text-stone-600">
        {items.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.nameKey}
              href={item.href}
              className={cn(
                "block rounded-xl px-3 py-2 transition-all",
                active
                  ? "bg-amber-100 text-amber-900 shadow-inner shadow-amber-200"
                  : "text-stone-600 hover:bg-amber-50/70 hover:text-amber-900",
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
