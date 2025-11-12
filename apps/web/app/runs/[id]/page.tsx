import RunDetail from '@/components/consultaion/consultaion/run-detail'
import { ReportButton } from './report-button'
import { getDebate, getReport } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function RunDetailPage({ params }: { params: { id: string } }) {
  const [debate, report] = await Promise.all([getDebate(params.id), getReport(params.id)])

  return (
    <main id="main" className="space-y-6 p-4">
      <RunDetail debate={debate} report={report} />
      <ReportButton debateId={params.id} apiBase={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'} />
    </main>
  )
}
