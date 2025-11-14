import RunsTable from '@/components/consultaion/consultaion/runs-table'
import { getMe } from '@/lib/auth'
import { getMyDebates } from '@/lib/api'

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

  const data = await getMyDebates({ limit: 50, offset: 0 })
  const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []

  return (
    <main id="main" className="h-full space-y-6 py-6">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Your archive</p>
        <h1 className="mt-1 text-3xl font-semibold text-stone-900">Saved runs</h1>
        <p className="text-sm text-stone-600">Only debates you convened are visible here.</p>
      </header>
      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <RunsTable items={items} />
      </section>
    </main>
  )
}
