import RunsTable from '@/components/consultaion/consultaion/runs-table'
import { getDebates } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function RunsPage() {
  const data = await getDebates({ limit: 50, offset: 0 })
  const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []

  return (
    <main id="main" className="h-full py-6">
      <div className="px-4">
        <RunsTable items={items} />
      </div>
    </main>
  )
}
