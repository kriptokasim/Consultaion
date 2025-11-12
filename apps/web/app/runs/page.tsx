import RunsTable from '@/components/consultaion/consultaion/runs-table'
import { fetchWithAuth, getMe } from '@/lib/auth'

export const dynamic = 'force-dynamic'

export default async function RunsPage() {
  const profile = await getMe()
  if (!profile) {
    return (
      <main id="main" className="flex h-full items-center justify-center py-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">Please sign in to view your runs.</p>
          <a href="/login" className="mt-3 inline-flex items-center rounded bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Go to Login
          </a>
        </div>
      </main>
    )
  }

  const params = new URLSearchParams({ limit: '50', offset: '0' })
  const response = await fetchWithAuth(`/debates?${params.toString()}`)
  if (response.status === 401) {
    return (
      <main id="main" className="flex h-full items-center justify-center py-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">Session expired. Please sign in again.</p>
          <a href="/login" className="mt-3 inline-flex items-center rounded bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Go to Login
          </a>
        </div>
      </main>
    )
  }
  const data = await response.json()
  const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []

  return (
    <main id="main" className="h-full py-6">
      <div className="px-4">
        <RunsTable items={items} />
      </div>
    </main>
  )
}
