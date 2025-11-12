import VotingSection from '@/components/parliament/VotingSection'
import DebateView from '@/components/parliament/DebateView'
import type { ScoreItem, VotePayload, DebateEvent } from '@/components/parliament/types'
import { getDebate, getReport, getEvents } from '@/lib/api'
import { ReportButton } from './report-button'

export const dynamic = 'force-dynamic'

type RunDetailProps = {
  params: Promise<{ id: string }>
}

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await params
  const [debate, report, eventPayload] = await Promise.all([getDebate(id), getReport(id), getEvents(id)])

  const rawScores = Array.isArray(report?.scores) ? report.scores : []
  const scores: ScoreItem[] = rawScores.map((entry: any) => ({
    persona: entry.persona ?? 'Agent',
    score: typeof entry.score === 'number' ? entry.score : Number(entry.score ?? 0),
    rationale: entry.rationale,
  }))

  const ranking = scores.length ? [...scores].sort((a, b) => b.score - a.score).map((s) => s.persona) : []
  const vote: VotePayload | undefined = ranking.length ? { method: 'borda', ranking } : undefined

  const events: DebateEvent[] = Array.isArray(eventPayload?.items) ? eventPayload.items : []

  if (debate?.final_content) {
    events.push({
      type: 'final',
      actor: 'Synthesizer',
      role: 'synthesizer',
      text: debate.final_content,
    })
  }

  return (
    <main id="main" className="space-y-6 p-4">
      <VotingSection scores={scores} vote={vote} />
      <DebateView events={events} />
      <ReportButton debateId={id} apiBase={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'} />
    </main>
  )
}
