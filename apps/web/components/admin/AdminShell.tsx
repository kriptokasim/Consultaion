"use client"

import type { ReactNode } from "react"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

const navLinks = [
  { name: "Overview", href: "/admin" },
  { name: "Users", href: "/admin/users" },
  { name: "Models", href: "/admin/models" },
  { name: "Promotions", href: "/admin/promotions" },
]

type AdminShellProps = {
  children: ReactNode
  profile: { email: string; display_name?: string | null }
}

export default function AdminShell({ children, profile }: AdminShellProps) {
  const pathname = usePathname()
  return (
    <div className="px-4 py-6 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="rounded-3xl border border-amber-100 bg-white p-5 shadow-[0_10px_30px_rgba(15,23,42,0.08)] dark:border-stone-800 dark:bg-stone-950">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Admin Console</p>
              <p className="text-base font-semibold text-stone-900 dark:text-stone-100">{profile.display_name || profile.email}</p>
            </div>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">Admin</span>
          </div>
          <nav className="mt-5 space-y-1">
            {navLinks.map((item) => {
              const active = pathname === item.href
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "block rounded-2xl px-3 py-2 text-sm font-semibold transition",
                    active
                      ? "bg-gradient-to-r from-amber-100 to-amber-50 text-amber-900 shadow-inner shadow-amber-200"
                      : "text-stone-600 hover:bg-amber-50 hover:text-amber-900",
                  )}
                >
                  {item.name}
                </Link>
              )
            })}
          </nav>
        </aside>
        <section className="space-y-6">{children}</section>
      </div>
    </div>
  )
}
