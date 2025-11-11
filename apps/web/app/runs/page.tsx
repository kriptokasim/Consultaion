import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchDebates() {
  const res = await fetch(`${API}/debates?limit=50`, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error('Failed to load debates')
  }
  return res.json()
}

function formatDate(value?: string) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

export default async function RunsPage() {
  const debates = await fetchDebates()

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Recent Runs</h1>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Back to runner
        </Link>
      </div>
      <div className="overflow-x-auto border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="px-3 py-2">Prompt</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {debates.map((debate: any) => (
              <tr key={debate.id} className="border-t hover:bg-slate-50">
                <td className="px-3 py-2">
                  <Link href={`/runs/${debate.id}`} className="text-blue-600 hover:underline">
                    {debate.prompt.slice(0, 60)}{debate.prompt.length > 60 ? '…' : ''}
                  </Link>
                </td>
                <td className="px-3 py-2 capitalize">{debate.status}</td>
                <td className="px-3 py-2">{formatDate(debate.created_at)}</td>
                <td className="px-3 py-2">{formatDate(debate.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
