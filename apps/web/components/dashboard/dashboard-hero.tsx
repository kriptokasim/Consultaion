import { Button } from '@/components/ui/button'
import { Sparkles } from 'lucide-react'

interface DashboardHeroProps {
  email?: string | null
  onStartDebate: () => void
  recentCount?: number
}

export function DashboardHero({
  email,
  onStartDebate,
  recentCount = 0,
}: DashboardHeroProps) {
  return (
    <section className="animate-fade-in rounded-3xl border border-amber-200/60 bg-gradient-to-br from-white via-amber-50/40 to-[#f8e6c2] p-8 shadow-smooth-lg">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-amber-700 backdrop-blur-xs">
            <Sparkles className="h-3.5 w-3.5" />
            Welcome
          </div>
          <div>
            <h1 className="heading-serif text-fluid-3xl font-bold text-amber-950">
              Your Debate Cockpit
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-amber-900/80">
              Orchestrate multi-agent debates on any topic. Watch AI agents deliberate, judges score, and consensus emerge.
            </p>
          </div>
        </div>

        {email && (
          <div className="flex items-center gap-3 rounded-2xl border border-amber-200/60 bg-white/80 px-4 py-3 backdrop-blur-xs">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-amber-400 to-amber-600 text-white font-semibold shadow-inner">
              {email.charAt(0).toUpperCase()}
            </div>
            <div className="text-sm">
              <p className="font-semibold text-amber-900">{email}</p>
              <p className="text-xs text-amber-700/70">{recentCount} recent debate{recentCount !== 1 ? 's' : ''}</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <HeroStatCard label="Agents Debate" value="8" />
        <HeroStatCard label="Judges Score" value="3" />
        <HeroStatCard label="Rounds" value="4" />
      </div>
    </section>
  )
}

function HeroStatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="group rounded-xl border border-amber-200/40 bg-white/60 p-4 transition-all duration-300 hover:-translate-y-1 hover:border-amber-300 hover:shadow-smooth backdrop-blur-xs">
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-700/80">
        {label}
      </p>
      <p className="mt-2 text-3xl font-bold text-amber-900">{value}</p>
    </div>
  )
}
