import { fetchWithAuth, getMe } from '@/lib/auth'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function AdminPage() {
  const profile = await getMe()
  if (!profile || profile.role !== 'admin') {
    redirect('/login')
  }

  const res = await fetchWithAuth('/admin/users')
  if (res.status === 401 || res.status === 403) {
    redirect('/login')
  }
  const payload = await res.json()
  const users = Array.isArray(payload?.items) ? payload.items : []

  return (
    <main id="main" className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Admin Dashboard</h1>
        <p className="text-sm text-muted-foreground">Users, debate counts, and recent activity</p>
      </header>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-muted/40 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Debates</th>
              <th className="px-4 py-3">Last Activity</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-sm">
            {users.map((user: any) => (
              <tr key={user.id}>
                <td className="px-4 py-3 font-medium text-foreground">{user.email}</td>
                <td className="px-4 py-3">
                  <span className="rounded bg-secondary px-2 py-1 text-xs uppercase tracking-wide text-secondary-foreground">
                    {user.role}
                  </span>
                </td>
                <td className="px-4 py-3">{user.debate_count ?? 0}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {user.last_activity ? new Date(user.last_activity).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
            {users.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">
                  No users yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  )
}
