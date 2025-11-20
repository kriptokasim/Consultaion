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
  { name: "Ops & Health", href: "/admin/ops" },
]

type AdminShellProps = {
  children: ReactNode
  profile: { email: string; display_name?: string | null }
}

export default function AdminShell({ children, profile }: AdminShellProps) {
  const pathname = usePathname()
  return (
    <main className="app-surface min-h-screen px-4 py-8 lg:px-12">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="card-elevated space-y-5 p-6">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.4em] text-amber-600">Admin</p>
              <p className="heading-serif text-lg font-semibold text-amber-950 dark:text-amber-50">
                {profile.display_name || profile.email}
              </p>
            </div>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">Ops</span>
          </div>
          <nav className="space-y-1">
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
                      : "text-stone-600 hover:bg-amber-50/80 hover:text-amber-900",
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
    </main>
  )
}
