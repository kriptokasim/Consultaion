import AdminUsersClient from "@/components/admin/AdminUsersClient"
import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

export default async function AdminUsersPage() {
  const res = await fetchWithAuth("/admin/users")
  const payload = await res.json().catch(() => ({ items: [] }))
  return (
    <main id="main" className="space-y-6">
      <AdminUsersClient initialItems={payload.items || []} />
    </main>
  )
}
