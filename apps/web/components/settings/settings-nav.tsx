"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

const items = [
  { name: "Overview", href: "/settings" },
  { name: "Profile", href: "/settings/profile" },
  { name: "Billing", href: "/settings/billing" },
]

export default function SettingsNav() {
  const pathname = usePathname()
  return (
    <nav className="space-y-1 rounded-2xl border border-amber-100 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Settings</p>
      <div className="mt-3 space-y-1 text-sm font-semibold text-stone-600">
        {items.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "block rounded-xl px-3 py-2 transition-colors",
                active ? "bg-amber-100 text-amber-900 shadow-inner shadow-amber-200" : "hover:bg-amber-50 hover:text-amber-900",
              )}
            >
              {item.name}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
