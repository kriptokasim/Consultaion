import type { ReactNode } from "react"

import AdminShell from "@/components/admin/AdminShell"
import { getMe } from "@/lib/auth"
import { redirect } from "next/navigation"

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const profile = await getMe()
  if (!profile) {
    redirect("/login")
  }
  const isAdmin = profile?.is_admin || profile?.role === "admin"
  if (!isAdmin) {
    return (
      <main id="main" className="px-6 py-10">
        <div className="rounded-3xl border border-red-200 bg-white p-6 shadow-sm dark:border-red-900/60 dark:bg-stone-950">
          <p className="text-sm font-semibold text-red-700 dark:text-red-300">Access denied</p>
          <p className="text-sm text-stone-600 dark:text-stone-300">
            You need admin permissions to view this console. Ask an administrator to promote your account.
          </p>
        </div>
      </main>
    )
  }
  return <AdminShell profile={profile}>{children}</AdminShell>
}
