import { fetchWithAuth } from "@/lib/auth"

export const dynamic = "force-dynamic"

type PromotionItem = {
  id: string
  location: string
  title: string
  target_plan_slug?: string | null
  is_active: boolean
  priority?: number
}

export default async function AdminPromotionsPage() {
  const res = await fetchWithAuth("/admin/promotions")
  const payload = await res.json().catch(() => ({ items: [] }))
  const promotions: PromotionItem[] = payload.items || []

  return (
    <main id="main" className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Promotions</p>
        <h1 className="text-3xl font-semibold text-stone-900 dark:text-stone-100">Upsell blocks</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Monitor which promos are active across locations.</p>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        {promotions.map((promo) => (
          <div key={promo.id} className="rounded-3xl border border-amber-100 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-950">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-wide text-amber-700">{promo.location}</p>
                <p className="text-lg font-semibold text-stone-900 dark:text-stone-100">{promo.title}</p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  promo.is_active ? "bg-emerald-100 text-emerald-700" : "bg-stone-200 text-stone-600"
                }`}
              >
                {promo.is_active ? "Active" : "Paused"}
              </span>
            </div>
            <div className="mt-3 text-sm text-stone-600 dark:text-stone-300">
              <p>Target plan: {promo.target_plan_slug || "all"}</p>
              <p>Priority: {promo.priority ?? "—"}</p>
            </div>
          </div>
        ))}
        {!promotions.length ? <p className="text-sm text-stone-500">No promotions configured.</p> : null}
      </div>
    </main>
  )
}
