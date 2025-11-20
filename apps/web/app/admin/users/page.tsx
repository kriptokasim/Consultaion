import AdminUsersClient from "@/components/admin/AdminUsersClient"
import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

export default async function AdminUsersPage() {
  const res = await fetchWithAuth("/admin/users")
  const payload = await res.json().catch(() => ({ items: [] }))
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Users</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950 dark:text-amber-50">Accounts &amp; plans</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Search accounts, inspect billing, and review subscriptions.</p>
      </header>
      <AdminUsersClient initialItems={payload.items || []} />
    </div>
  )
}
