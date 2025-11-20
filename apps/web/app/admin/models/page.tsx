import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

type AdminModelItem = {
  id: string
  display_name: string
  provider: string
  is_default?: boolean
  tokens_used: number
  approx_cost_usd?: number | null
  tags?: string[]
}

export default async function AdminModelsPage() {
  const res = await fetchWithAuth("/admin/models")
  const payload = await res.json().catch(() => ({ items: [] }))
  const models: AdminModelItem[] = payload.items || []

  return (
    <main id="main" className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Models</p>
        <h1 className="text-3xl font-semibold text-stone-900 dark:text-stone-100">Model registry &amp; usage</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Inspect enabled providers and their recent token footprints.</p>
      </header>
      <div className="grid gap-4">
        {models.map((model) => (
          <div
            key={model.id}
            className="rounded-3xl border border-amber-100 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-950"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-lg font-semibold text-stone-900 dark:text-stone-100">{model.display_name}</p>
                <p className="text-sm text-stone-500">{model.provider}</p>
              </div>
              {model.is_default ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">Default</span> : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-6 text-sm text-stone-700 dark:text-stone-200">
              <div>
                <p className="text-xs uppercase tracking-wide text-stone-500">Tokens used</p>
                <p className="font-semibold">{Intl.NumberFormat().format(model.tokens_used)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-stone-500">Approx cost</p>
                <p className="font-semibold">
                  {model.approx_cost_usd != null ? `$${model.approx_cost_usd.toFixed(2)}` : "—"}
                </p>
              </div>
              {model.tags?.length ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-stone-500">Tags</p>
                  <div className="flex flex-wrap gap-2">
                    {model.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ))}
        {!models.length ? <p className="text-sm text-stone-500">No models are enabled.</p> : null}
      </div>
    </main>
  )
}
