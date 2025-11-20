import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

type AdminUsersResponse = {
  items: Array<{ email: string; is_admin?: boolean; plan?: { slug: string | null } }>
  total?: number
}

type AdminModelsResponse = {
  totals?: { tokens_used?: number }
  items?: Array<{ id: string; tokens_used: number }>
}

export default async function AdminOverviewPage() {
  const [usersRes, modelsRes] = await Promise.all([fetchWithAuth("/admin/users"), fetchWithAuth("/admin/models")])
  const usersPayload = (await usersRes.json().catch(() => ({ items: [] }))) as AdminUsersResponse
  const modelsPayload = (await modelsRes.json().catch(() => ({ items: [] }))) as AdminModelsResponse

  const users = usersPayload.items || []
  const totalUsers = usersPayload.total ?? users.length
  const adminCount = users.filter((user) => user.is_admin).length
  const planMix = users.reduce<Record<string, number>>((acc, user) => {
    const slug = user.plan?.slug || "unassigned"
    acc[slug] = (acc[slug] || 0) + 1
    return acc
  }, {})
  const tokensUsed = modelsPayload.totals?.tokens_used || 0
  const topModels = (modelsPayload.items || []).sort((a, b) => b.tokens_used - a.tokens_used).slice(0, 3)

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Admin overview</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950 dark:text-amber-50">Parliament control tower</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Snapshot of users, billing mix, and chamber usage.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard label="Total users" value={totalUsers} description={`${adminCount} admin seats`} />
        <StatCard label="Admin seats" value={adminCount} description="Operators with console access" />
        <StatCard label="Tokens used (month)" value={Intl.NumberFormat().format(tokensUsed)} description="Approximate across all models" />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Plan mix</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">Breakdown of active plans among current users.</p>
          <div className="mt-4 space-y-2">
            {Object.entries(planMix).map(([slug, count]) => (
              <div key={slug} className="flex items-center justify-between rounded-2xl bg-amber-50/60 px-3 py-2 text-sm font-semibold text-amber-900">
                <span>{slug}</span>
                <span>{count}</span>
              </div>
            ))}
            {Object.keys(planMix).length === 0 ? <p className="text-sm text-stone-500">No users yet.</p> : null}
          </div>
        </div>
        <div className="card-elevated p-5">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Top models this period</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400">Quick glance at token-heavy models.</p>
          <div className="mt-4 space-y-2">
            {topModels.length ? (
              topModels.map((model) => (
                <div key={model.id} className="flex items-center justify-between rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-stone-700 shadow-inner shadow-amber-100">
                  <span>{model.id}</span>
                  <span>{Intl.NumberFormat().format(model.tokens_used)}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-stone-500">No usage recorded.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function StatCard({ label, value, description }: { label: string; value: number | string; description?: string }) {
  return (
    <div className="glass-card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-stone-900 dark:text-stone-100">{value}</p>
      {description ? <p className="text-sm text-stone-500 dark:text-stone-400">{description}</p> : null}
    </div>
  )
}
