import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

type AdminModelItem = {
  id: string
  display_name: string
  provider: string
  is_default?: boolean
  recommended?: boolean
  tokens_used: number
  approx_cost_usd?: number | null
  tags?: string[]
  tiers?: {
    cost: "low" | "medium" | "high"
    latency: "fast" | "normal" | "slow"
    quality: "baseline" | "advanced" | "flagship"
    safety: "strict" | "normal" | "experimental"
  }
}

export default async function AdminModelsPage() {
  const res = await fetchWithAuth("/admin/models")
  const payload = await res.json().catch(() => ({ items: [] }))
  const models: AdminModelItem[] = payload.items || []

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Models</p>
        <h1 className="heading-serif text-3xl font-semibold text-amber-950 dark:text-amber-50">Model registry &amp; usage</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Inspect enabled providers, capabilities, and routing tiers.</p>
      </header>
      <div className="grid gap-4">
        {models.map((model) => (
          <div
            key={model.id}
            className="glass-card p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-lg font-semibold text-stone-900 dark:text-stone-100 flex items-center gap-2">
                    {model.display_name}
                    {model.recommended ? (
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-700">Recommended</span>
                    ) : null}
                  </p>
                  <p className="text-sm text-stone-500">{model.provider}</p>
                </div>
              </div>
              {model.is_default ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">Default</span> : null}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {model.tiers ? (
                <>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-stone-500">Quality</p>
                    <p className="font-medium capitalize">{model.tiers.quality}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-stone-500">Cost</p>
                    <p className="font-medium capitalize">{model.tiers.cost}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-stone-500">Latency</p>
                    <p className="font-medium capitalize">{model.tiers.latency}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-stone-500">Safety</p>
                    <p className="font-medium capitalize">{model.tiers.safety}</p>
                  </div>
                </>
              ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-6 text-sm text-stone-700 dark:text-stone-200 pt-4 border-t border-stone-100 dark:border-stone-800">
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
                  <p className="text-xs uppercase tracking-wide text-stone-500">Capabilities</p>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {model.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800 border border-amber-100">
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
    </div>
  )
}
