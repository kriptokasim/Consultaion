import Link from 'next/link'
import { ReportButton } from './report-button'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchJSON(path: string) {
  const res = await fetch(`${API}${path}`, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error(`Failed to load ${path}`)
  }
  return res.json()
}

function formatDate(value?: string) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

export default async function RunDetail({ params }: { params: { id: string } }) {
  const [debate, report] = await Promise.all([
    fetchJSON(`/debates/${params.id}`),
    fetchJSON(`/debates/${params.id}/report`)
  ])
  const scores = report?.scores ?? []

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Run Detail</h1>
          <p className="text-sm text-slate-600">Debate ID: {debate.id}</p>
        </div>
        <Link href="/runs" className="text-sm text-blue-600 hover:underline">
          ← Back to runs
        </Link>
      </div>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Prompt</h2>
        <p className="rounded border p-3 text-sm bg-white">{debate.prompt}</p>
        <p className="text-sm text-slate-600">
          Status: <span className="font-semibold capitalize">{debate.status}</span> · Created {formatDate(debate.created_at)}
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Final Answer</h2>
        <pre className="rounded border p-3 bg-white whitespace-pre-wrap text-sm">{debate.final_content || 'Pending'}</pre>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Scores</h2>
        <div className="overflow-x-auto border rounded">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-3 py-2">Persona</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {scores.map((score: any, idx: number) => (
                <tr key={idx} className="border-t">
                  <td className="px-3 py-2">{score.persona}</td>
                  <td className="px-3 py-2">{score.score}</td>
                  <td className="px-3 py-2">{score.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <ReportButton debateId={params.id} apiBase={API} />
    </main>
  )
}
